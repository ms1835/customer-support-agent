import operator
import os
import re
from typing import Annotated, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg_pool import ConnectionPool
from sqlalchemy.orm import Session

from app.models.conversations import Conversation, ConversationStatus
from app.models.support_tickets import EscalationType, TicketPriority
from app.rag.retrieval import retrieve_relevant_chunks
from app.services.escalation_service import EscalationService
from app.services.llm_service import generate_intent, generate_response
from app.tools.support_tools import (
    cancel_order_action,
    get_order_details,
    get_order_status,
    get_shipment_status,
    initiate_return_action,
    refund_order_action,
)

_ORDER_RE = re.compile(r"#?(\d{3,})")

_INTENT_TOPIC: dict[str, str] = {
    "documentation": "product policy and documentation",
    "return": "return policy and return request",
    "refund": "refund policy and refund request",
    "cancel": "cancellation policy and order cancellation",
    "order": "order details and status",
    "shipment": "shipment tracking and delivery",
}

# Shared by conversation_service and streaming routes.
PENDING_APPROVAL_MESSAGE = (
    "Your request has been received and is pending approval. "
    "Please review the details and approve or reject below."
)

# Keywords that trigger auto-escalation regardless of classified intent.
_FRUSTRATION_PATTERNS = re.compile(
    r"\b(this is ridiculous|unacceptable|speak to a manager|terrible service|"
    r"worst|i am furious|so angry|fed up|useless|incompetent|escalate)\b",
    re.IGNORECASE,
)


class AgentState(TypedDict):
    messages: list[str]
    history: Annotated[list[dict], operator.add]
    user_id: str
    conversation_id: str
    intent: str | None
    order_number: str | None
    retrieved_documents: list
    tool_result: dict | None
    action_result: dict | None
    requires_approval: bool
    approval_status: str | None
    final_response: str | None
    # Escalation fields
    escalation_ticket_id: int | None
    assigned_agent_name: str | None
    auto_escalate: bool  # set by routing when auto-escalation is triggered


POLICY_INTENTS = {"documentation"}
APPROVAL_INTENTS = {"cancel", "refund", "return"}
RETRIEVE_INTENTS = POLICY_INTENTS | APPROVAL_INTENTS
TOOL_INTENTS = {"order", "shipment"}
ESCALATION_INTENTS = {"human"}

_checkpointer: PostgresSaver | None = None
_pool: ConnectionPool | None = None


def _get_checkpointer() -> PostgresSaver:
    global _checkpointer, _pool
    if _checkpointer is None:
        conn_string = os.environ.get("DATABASE_URL", "")
        _pool = ConnectionPool(conninfo=conn_string, max_size=10, kwargs={"autocommit": True})
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()
        print("[checkpointer] PostgresSaver initialised and tables ensured.")
    return _checkpointer


def _extract_order_from_history(history: list[dict]) -> str | None:
    for turn in reversed(history):
        if turn.get("role") == "user":
            m = _ORDER_RE.search(turn["content"])
            if m:
                return m.group(0).lstrip("#")
    return None


def _should_auto_escalate(message: str) -> bool:
    """Return True when the message contains strong frustration signals."""
    return bool(_FRUSTRATION_PATTERNS.search(message))


def build_support_graph(db: Session):

    # ------------------------------------------------------------------ nodes

    def guard_node(state: AgentState) -> dict:
        """
        Entry guard — runs before classify.
        If the conversation is already escalated, emit an SSE event and
        short-circuit with a final_response so the graph ends without
        invoking the bot.
        """
        write = get_stream_writer()
        conversation_id = int(state["conversation_id"])
        conversation = db.get(Conversation, conversation_id)

        if conversation and conversation.status == ConversationStatus.ESCALATED:
            print("[ROUTE] guard → conversation already escalated, short-circuiting")
            write({"event": "escalated", "data": {
                "message": "Your conversation is being handled by a human support agent.",
            }})
            return {
                "intent": "already_escalated",
                "final_response": (
                    "Your conversation is currently being handled by one of our "
                    "human support agents. They will respond to you shortly. "
                    "Please wait — you do not need to send another message."
                ),
            }
        return {}

    def classify_node(state: AgentState) -> dict:
        write = get_stream_writer()
        print("\n[ROUTE] guard → classify")
        write({"event": "thinking", "data": {"message": "Classifying your request..."}})

        user_message = state["messages"][-1]
        history = state.get("history", [])
        intent = generate_intent(user_message, history=history)
        category = "cancel" if intent.category == "cancellation" else intent.category
        order_number = intent.order_number or _extract_order_from_history(history)

        # Check auto-escalation: frustration keywords override the classified intent.
        auto_escalate = _should_auto_escalate(user_message)
        if auto_escalate:
            print(f"[ROUTE] classify → AUTO-ESCALATE (intent was {category!r})")

        print(f"[ROUTE] classify → intent={category!r} order={order_number!r} auto_escalate={auto_escalate}")
        return {"intent": category, "order_number": order_number, "auto_escalate": auto_escalate}

    def retrieve_node(state: AgentState) -> dict:
        write = get_stream_writer()
        print("[ROUTE] → retrieve")
        write({"event": "retrieving_documents", "data": {"message": "Searching knowledge base..."}})

        intent = state["intent"]
        user_message = state["messages"][-1]
        topic = _INTENT_TOPIC.get(intent, intent)
        query = f"{topic}: {user_message}"
        try:
            documents = retrieve_relevant_chunks(db, query)
        except Exception as exc:
            print(f"RAG retrieval failed ({exc}); continuing without docs.")
            documents = []
        print(f"RAG intent={intent!r} docs={len(documents)} query={query!r}")
        return {"retrieved_documents": documents}

    def tool_node(state: AgentState) -> dict:
        write = get_stream_writer()
        print("[ROUTE] → tool")
        intent = state["intent"]
        order_number = state["order_number"]

        if not order_number:
            print("[tool_node] No order number — skipping tool call.")
            return {"tool_result": {"error": "no_order_number"}}

        if intent == "shipment":
            tool_name = "get_shipment_status"
        elif intent in APPROVAL_INTENTS:
            tool_name = "get_order_details"
        elif any(kw in state["messages"][-1].lower() for kw in ("status", "where", "track", "delivered")):
            tool_name = "get_order_status"
        else:
            tool_name = "get_order_details"

        write({"event": "tool_started", "data": {"tool": tool_name}})
        print(f"[tool_node] Calling {tool_name}(order={order_number!r})")

        try:
            if tool_name == "get_shipment_status":
                result = get_shipment_status(db, order_number)
            elif tool_name == "get_order_status":
                result = get_order_status(db, order_number)
            else:
                result = get_order_details(db, order_number)
        except ValueError as exc:
            print(f"[tool_node] Tool raised ValueError: {exc}")
            write({"event": "tool_completed", "data": {"tool": tool_name, "error": str(exc)}})
            return {"tool_result": {"error": str(exc)}}

        if result is None:
            print(f"[tool_node] Order {order_number!r} not found.")
            write({"event": "tool_completed", "data": {"tool": tool_name, "error": "not_found"}})
            return {"tool_result": {"error": f"order_{order_number}_not_found"}}

        print(f"[tool_node] Tool result: {result}")
        write({"event": "tool_completed", "data": {"tool": tool_name}})
        return {"tool_result": result}

    def approval_node(state: AgentState) -> dict:
        write = get_stream_writer()
        print("[ROUTE] → approval (interrupt — waiting for human decision)")

        write({"event": "approval_required", "data": {
            "action": state["intent"],
            "order_number": state["order_number"],
            "order_data": state.get("tool_result"),
            "prompt": f"Approve {state['intent']} for order #{state['order_number']}?",
        }})

        decision = interrupt({
            "action": state["intent"],
            "order_number": state["order_number"],
            "order_data": state.get("tool_result"),
        })
        approved = isinstance(decision, dict) and decision.get("decision") == "approve"
        status = "approved" if approved else "rejected"
        print(f"[ROUTE] approval resumed → status={status!r}")
        return {"requires_approval": True, "approval_status": status}

    def execute_action_node(state: AgentState) -> dict:
        write = get_stream_writer()
        print("[ROUTE] → execute_action")
        intent = state["intent"]
        order_number = state["order_number"]
        action_name = f"{intent}_order"

        if state.get("approval_status") != "approved":
            print("[execute_action] Rejected — skipping action.")
            write({"event": "tool_completed", "data": {"tool": action_name, "skipped": True}})
            return {"action_result": {"action": "rejected"}}

        write({"event": "tool_started", "data": {"tool": action_name}})
        try:
            if intent == "cancel":
                result = cancel_order_action(db, order_number)
            elif intent == "refund":
                result = refund_order_action(db, order_number)
            elif intent == "return":
                result = initiate_return_action(db, order_number)
            else:
                result = {"error": f"unknown_action_{intent}"}
        except Exception as exc:
            print(f"[execute_action] Exception: {exc}")
            result = {"error": str(exc)}

        print(f"[execute_action] Result: {result}")
        write({"event": "tool_completed", "data": {"tool": action_name}})
        return {"action_result": result, "tool_result": result}

    def escalation_node(state: AgentState) -> dict:
        """
        Escalate conversation to a human agent:
        1. Emit escalation_started SSE
        2. Call EscalationService — creates SupportTicket, auto-assigns agent
        3. Emit escalation_complete SSE with ticket_id and agent name
        """
        write = get_stream_writer()
        print("[ROUTE] → escalation")
        write({"event": "escalation_started", "data": {
            "message": "Connecting you with a human support agent...",
        }})

        conversation_id = int(state["conversation_id"])
        auto_escalate = state.get("auto_escalate", False)
        intent = state.get("intent", "human")

        # Determine escalation type and build a human-readable reason.
        if auto_escalate:
            escalation_type = EscalationType.AUTO_SENTIMENT
            reason = "Auto-escalated: high frustration detected in user message."
        else:
            escalation_type = EscalationType.USER_REQUESTED
            reason = "User requested to speak with a human support agent."

        try:
            svc = EscalationService(db)
            ticket = svc.escalate_conversation(
                conversation_id=conversation_id,
                reason=reason,
                escalation_type=escalation_type,
                priority=TicketPriority.HIGH if auto_escalate else TicketPriority.MEDIUM,
            )

            # Load agent name — assigned_agent may be None if no one is available.
            agent_name: str | None = None
            if ticket.assigned_agent_id:
                db.refresh(ticket)
                agent_name = ticket.assigned_agent.name if ticket.assigned_agent else None

            print(f"[escalation_node] Ticket #{ticket.id} created, agent={agent_name!r}")
            write({"event": "escalation_complete", "data": {
                "ticket_id": ticket.id,
                "assigned_agent": agent_name,
                "message": (
                    f"You've been connected with {agent_name}. They'll be with you shortly."
                    if agent_name
                    else "A support agent will be with you shortly."
                ),
            }})
            return {
                "escalation_ticket_id": ticket.id,
                "assigned_agent_name": agent_name,
            }

        except Exception as exc:
            print(f"[escalation_node] Failed to create ticket: {exc}")
            write({"event": "escalation_complete", "data": {
                "error": "Unable to connect right now. Please try again.",
            }})
            return {"escalation_ticket_id": None, "assigned_agent_name": None}

    def response_node(state: AgentState) -> dict:
        print("[ROUTE] → response")
        intent = state["intent"]
        current_message = state["messages"][-1]

        if intent == "already_escalated":
            # guard_node already set final_response — just flush history.
            response = state["final_response"]
        elif intent == "human":
            agent_name = state.get("assigned_agent_name")
            ticket_id = state.get("escalation_ticket_id")
            if agent_name and ticket_id:
                response = (
                    f"I've connected you with {agent_name}, one of our human support specialists "
                    f"(Ticket #{ticket_id}). They'll review your case and respond shortly. "
                    f"You can continue in this conversation."
                )
            else:
                response = (
                    "I've escalated your conversation to our human support team. "
                    "A specialist will be with you shortly."
                )
        elif intent == "unknown":
            response = (
                "I can only help with orders, shipments, returns, refunds, "
                "cancellations, and product policy questions. "
                "Please let me know if I can assist with any of those."
            )
        elif intent in APPROVAL_INTENTS and not state.get("order_number"):
            response = "Please provide your order number so I can look into that for you."
        elif intent in POLICY_INTENTS and not state["retrieved_documents"]:
            response = (
                "I don't have documentation available to answer that question. "
                "Please contact our support team for more information."
            )
        else:
            intent_obj = type("_Intent", (), {
                "category": intent,
                "order_number": state["order_number"],
            })()
            response = generate_response(
                message=current_message,
                intent=intent_obj,
                context=state["retrieved_documents"],
                tool_result=state["tool_result"],
                history=state.get("history", []),
                requires_approval=state.get("requires_approval", False),
            )

        new_history_delta = [
            {"role": "user", "content": current_message},
            {"role": "assistant", "content": response},
        ]
        return {"final_response": response, "history": new_history_delta}

    # ------------------------------------------------------------------ routing

    def route_after_guard(state: AgentState) -> str:
        """Skip classify + bot entirely if conversation is already escalated."""
        if state.get("intent") == "already_escalated":
            return "response"
        return "classify"

    def route_after_classify(state: AgentState) -> str:
        intent = state["intent"]
        # Auto-escalation overrides the classified intent.
        if state.get("auto_escalate") or intent in ESCALATION_INTENTS:
            next_node = "escalation"
        elif intent in RETRIEVE_INTENTS:
            next_node = "retrieve"
        elif intent in TOOL_INTENTS:
            next_node = "tool"
        else:
            next_node = "response"
        print(f"[ROUTE] classify → {next_node}")
        return next_node

    def route_after_retrieve(state: AgentState) -> str:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            next_node = "tool" if state["order_number"] else "response"
        else:
            next_node = "response"
        print(f"[ROUTE] retrieve → {next_node}")
        return next_node

    def route_after_tool(state: AgentState) -> str:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            tool_result = state.get("tool_result") or {}
            next_node = "approval" if "error" not in tool_result else "response"
        else:
            next_node = "response"
        print(f"[ROUTE] tool → {next_node}")
        return next_node

    # ------------------------------------------------------------------ graph

    graph = StateGraph(AgentState)
    graph.add_node("guard", guard_node)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("approval", approval_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("response", response_node)

    graph.add_edge(START, "guard")
    graph.add_conditional_edges(
        "guard", route_after_guard,
        {"classify": "classify", "response": "response"},
    )
    graph.add_conditional_edges(
        "classify", route_after_classify,
        {"retrieve": "retrieve", "tool": "tool",
         "escalation": "escalation", "response": "response"},
    )
    graph.add_conditional_edges(
        "retrieve", route_after_retrieve,
        {"tool": "tool", "response": "response"},
    )
    graph.add_conditional_edges(
        "tool", route_after_tool,
        {"approval": "approval", "response": "response"},
    )
    graph.add_edge("approval", "execute_action")
    graph.add_edge("execute_action", "response")
    graph.add_edge("escalation", "response")
    graph.add_edge("response", END)
    return graph.compile(checkpointer=_get_checkpointer())


# ---------------------------------------------------------------------------
# Invoke helpers (non-streaming — used by existing REST endpoints)
# ---------------------------------------------------------------------------

def run_support_graph(db: Session, message: str, user_id: str, conversation_id: str) -> AgentState:
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    print(f"[checkpointer] Invoking graph thread_id={conversation_id!r}")
    return graph.invoke(
        {
            "messages": [message],
            "history": [],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "intent": None,
            "order_number": None,
            "retrieved_documents": [],
            "tool_result": None,
            "action_result": None,
            "requires_approval": False,
            "approval_status": None,
            "final_response": None,
            "escalation_ticket_id": None,
            "assigned_agent_name": None,
            "auto_escalate": False,
        },
        config=config,
    )


def resume_support_graph(db: Session, conversation_id: str, decision: str) -> AgentState:
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    print(f"[checkpointer] Resuming graph thread_id={conversation_id!r} decision={decision!r}")
    return graph.invoke(Command(resume={"decision": decision}), config=config)


# ---------------------------------------------------------------------------
# Stream helpers — used by SSE endpoints
# ---------------------------------------------------------------------------

_INITIAL_STATE_KEYS = {
    "history": [],
    "intent": None,
    "order_number": None,
    "retrieved_documents": [],
    "tool_result": None,
    "action_result": None,
    "requires_approval": False,
    "approval_status": None,
    "final_response": None,
    "escalation_ticket_id": None,
    "assigned_agent_name": None,
    "auto_escalate": False,
}


def stream_support_graph(db: Session, message: str, user_id: str, conversation_id: str):
    """Yields (mode, data) tuples from graph.stream()."""
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    state = {
        **_INITIAL_STATE_KEYS,
        "messages": [message],
        "user_id": user_id,
        "conversation_id": conversation_id,
    }
    print(f"[stream] Starting stream thread_id={conversation_id!r}")
    yield from graph.stream(state, config=config, stream_mode=["custom", "messages", "updates"])


def stream_resume_graph(db: Session, conversation_id: str, decision: str):
    """Yields (mode, data) tuples resuming from an interrupt checkpoint."""
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    print(f"[stream] Resuming stream thread_id={conversation_id!r} decision={decision!r}")
    yield from graph.stream(
        Command(resume={"decision": decision}),
        config=config,
        stream_mode=["custom", "messages", "updates"],
    )
