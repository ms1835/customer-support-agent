import operator
import os
import re
from typing import Annotated, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg_pool import ConnectionPool
from sqlalchemy.orm import Session

from app.rag.retrieval import retrieve_relevant_chunks
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

# Topic labels used to anchor RAG embeddings for follow-up questions.
_INTENT_TOPIC: dict[str, str] = {
    "documentation": "product policy and documentation",
    "return": "return policy and return request",
    "refund": "refund policy and refund request",
    "cancel": "cancellation policy and order cancellation",
    "order": "order details and status",
    "shipment": "shipment tracking and delivery",
}


class AgentState(TypedDict):
    messages: list[str]
    # Annotated with operator.add so LangGraph appends deltas across checkpoint
    # turns instead of overwriting — the full conversation history grows here.
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


# Pure policy / FAQ — only RAG, no action needed.
POLICY_INTENTS = {"documentation"}
# Customer-initiated actions — RAG + tool lookup + human-approval gate.
APPROVAL_INTENTS = {"cancel", "refund", "return"}
RETRIEVE_INTENTS = POLICY_INTENTS | APPROVAL_INTENTS
TOOL_INTENTS = {"order", "shipment"}
ESCALATION_INTENTS = {"human"}


_checkpointer: PostgresSaver | None = None
_pool: ConnectionPool | None = None


def _get_checkpointer() -> PostgresSaver:
    """Lazy singleton — creates the connection pool and PostgresSaver once."""
    global _checkpointer, _pool
    if _checkpointer is None:
        conn_string = os.environ.get("DATABASE_URL", "")
        _pool = ConnectionPool(
            conninfo=conn_string,
            max_size=10,
            kwargs={"autocommit": True},
        )
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()   # creates checkpoint tables if they don't exist
        print("[checkpointer] PostgresSaver initialised and tables ensured.")
    return _checkpointer


def _extract_order_from_history(history: list[dict]) -> str | None:
    """Scan prior user turns (newest-first) for a previously mentioned order number."""
    for turn in reversed(history):
        if turn.get("role") == "user":
            m = _ORDER_RE.search(turn["content"])
            if m:
                return m.group(0).lstrip("#")
    return None


def build_support_graph(db: Session):

    def classify_node(state: AgentState) -> dict:
        print("\n[ROUTE] START → classify")
        user_message = state["messages"][-1]
        history = state.get("history", [])
        intent = generate_intent(user_message, history=history)
        # Normalise legacy "cancellation" to "cancel"
        category = "cancel" if intent.category == "cancellation" else intent.category
        # Carry forward the order number from history when the customer omits it
        order_number = intent.order_number or _extract_order_from_history(history)
        print(f"[ROUTE] classify → intent={category!r} order={order_number!r}")
        return {"intent": category, "order_number": order_number}

    def retrieve_node(state: AgentState) -> dict:
        print("[ROUTE] → retrieve")
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
        print("[ROUTE] → tool")
        intent = state["intent"]
        order_number = state["order_number"]
        if not order_number:
            print("[tool_node] No order number in state — skipping tool call.")
            return {"tool_result": {"error": "no_order_number"}}

        try:
            if intent == "shipment":
                print(f"[tool_node] Calling get_shipment_status(order={order_number!r})")
                result = get_shipment_status(db, order_number)
            elif intent in APPROVAL_INTENTS:
                print(f"[tool_node] Calling get_order_details(order={order_number!r}) for intent={intent!r}")
                result = get_order_details(db, order_number)
            elif any(
                kw in state["messages"][-1].lower()
                for kw in ("status", "where", "track", "delivered")
            ):
                print(f"[tool_node] Calling get_order_status(order={order_number!r})")
                result = get_order_status(db, order_number)
            else:
                print(f"[tool_node] Calling get_order_details(order={order_number!r})")
                result = get_order_details(db, order_number)
        except ValueError as exc:
            print(f"[tool_node] Tool raised ValueError: {exc}")
            return {"tool_result": {"error": str(exc)}}

        if result is None:
            print(f"[tool_node] Tool returned None — order {order_number!r} not found.")
            return {"tool_result": {"error": f"order_{order_number}_not_found"}}

        print(f"[tool_node] Tool result: {result}")
        return {"tool_result": result}

    def approval_node(state: AgentState) -> dict:
        """
        Pause execution and wait for human approval via LangGraph interrupt.
        The graph is suspended here; resumption requires:
          graph.invoke(Command(resume={"decision": "approve"|"reject"}), config)
        """
        print("[ROUTE] → approval (interrupt — waiting for human decision)")
        decision = interrupt({
            "action": state["intent"],
            "order_number": state["order_number"],
            "order_data": state.get("tool_result"),
            "prompt": (
                f"Approve {state['intent']} request for order "
                f"#{state['order_number']}?"
            ),
        })
        approved = isinstance(decision, dict) and decision.get("decision") == "approve"
        status = "approved" if approved else "rejected"
        print(f"[ROUTE] approval resumed → decision={decision!r} status={status!r}")
        return {"requires_approval": True, "approval_status": status}

    def execute_action_node(state: AgentState) -> dict:
        """Execute the actual cancel/refund/return after human approval."""
        print("[ROUTE] → execute_action")
        if state.get("approval_status") != "approved":
            print("[execute_action] Rejected — skipping action.")
            return {"action_result": {"action": "rejected"}}

        intent = state["intent"]
        order_number = state["order_number"]

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
        # Overwrite tool_result so response_node sees the final action outcome
        return {"action_result": result, "tool_result": result}

    def escalation_node(state: AgentState) -> dict:
        print("[ROUTE] → escalation")
        return {"requires_approval": False, "approval_status": "escalated_to_human"}

    def response_node(state: AgentState) -> dict:
        print("[ROUTE] → response")
        intent = state["intent"]
        current_message = state["messages"][-1]

        if intent == "human":
            response = (
                "I'm connecting you with a human support specialist for a more "
                "detailed review of this issue."
            )
        elif intent == "unknown":
            response = (
                "I can only help with orders, shipments, returns, refunds, "
                "cancellations, and product policy questions. "
                "Please let me know if I can assist with any of those."
            )
        elif intent in APPROVAL_INTENTS and not state.get("order_number"):
            response = (
                "Please provide your order number so I can look into that for you."
            )
        elif intent in POLICY_INTENTS and not state["retrieved_documents"]:
            # No RAG context — refuse to answer from training data.
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

        # Persist this turn into the checkpointed history.
        new_history_delta = [
            {"role": "user", "content": current_message},
            {"role": "assistant", "content": response},
        ]
        return {"final_response": response, "history": new_history_delta}

    # ------------------------------------------------------------------ routing

    def route_after_classify(state: AgentState) -> str:
        intent = state["intent"]
        if intent in RETRIEVE_INTENTS:
            next_node = "retrieve"
        elif intent in TOOL_INTENTS:
            next_node = "tool"
        elif intent in ESCALATION_INTENTS:
            next_node = "escalation"
        else:
            next_node = "response"
        print(f"[ROUTE] classify → {next_node}")
        return next_node

    def route_after_retrieve(state: AgentState) -> str:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            # Need an order number to look up details and proceed to approval
            next_node = "tool" if state["order_number"] else "response"
        else:
            next_node = "response"
        print(f"[ROUTE] retrieve → {next_node}")
        return next_node

    def route_after_tool(state: AgentState) -> str:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            tool_result = state.get("tool_result") or {}
            # Only proceed to approval when order was found and has no error
            next_node = "approval" if "error" not in tool_result else "response"
        else:
            next_node = "response"
        print(f"[ROUTE] tool → {next_node}")
        return next_node

    # ------------------------------------------------------------------ graph

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("approval", approval_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("response", response_node)

    graph.add_edge(START, "classify")
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


def run_support_graph(
    db: Session,
    message: str,
    user_id: str,
    conversation_id: str,
) -> AgentState:
    """
    conversation_id → thread_id → LangGraph checkpoint.
    History is restored from the PostgreSQL checkpoint automatically.
    May raise GraphInterrupt if an approval interrupt is hit.
    """
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    print(f"[checkpointer] Invoking graph with thread_id={conversation_id!r}")
    return graph.invoke(
        {
            "messages": [message],
            "history": [],          # operator.add: appends [] → preserves checkpoint history
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
        },
        config=config,
    )


def resume_support_graph(
    db: Session,
    conversation_id: str,
    decision: str,
) -> AgentState:
    """
    Resume a graph that was paused by interrupt() in approval_node.
    decision: "approve" | "reject"
    """
    graph = build_support_graph(db)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    print(f"[checkpointer] Resuming graph thread_id={conversation_id!r} decision={decision!r}")
    return graph.invoke(
        Command(resume={"decision": decision}),
        config=config,
    )
