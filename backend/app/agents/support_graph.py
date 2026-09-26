import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.rag.retrieval import retrieve_relevant_chunks
from app.services.llm_service import generate_intent, generate_response
from app.tools.support_tools import (
    get_order_details,
    get_order_status,
    get_shipment_status,
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
    history: list[dict]        # [{"role": "user"|"assistant", "content": str}, ...]
    user_id: str
    conversation_id: str
    intent: str | None
    order_number: str | None
    retrieved_documents: list
    tool_result: dict | None
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
        user_message = state["messages"][-1]
        history = state.get("history", [])
        intent = generate_intent(user_message, history=history)
        # Normalise legacy "cancellation" to "cancel"
        category = "cancel" if intent.category == "cancellation" else intent.category
        # Carry forward the order number from history when the customer omits it
        order_number = intent.order_number or _extract_order_from_history(history)
        return {"intent": category, "order_number": order_number}

    def retrieve_node(state: AgentState) -> dict:
        intent = state["intent"]
        user_message = state["messages"][-1]
        # Anchor the embedding to the intent topic so short follow-ups like
        # "How long does it take?" still retrieve the right policy document.
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
        intent = state["intent"]
        order_number = state["order_number"]
        if not order_number:
            return {"tool_result": {"error": "no_order_number"}}

        try:
            if intent == "shipment":
                result = get_shipment_status(db, order_number)
            elif intent in APPROVAL_INTENTS:
                result = get_order_details(db, order_number)
            elif any(
                kw in state["messages"][-1].lower()
                for kw in ("status", "where", "track", "delivered")
            ):
                result = get_order_status(db, order_number)
            else:
                result = get_order_details(db, order_number)
        except ValueError as exc:
            return {"tool_result": {"error": str(exc)}}

        if result is None:
            return {"tool_result": {"error": f"order_{order_number}_not_found"}}
        return {"tool_result": result}

    def approval_node(state: AgentState) -> dict:
        return {"requires_approval": True, "approval_status": "pending"}

    def escalation_node(state: AgentState) -> dict:
        return {"requires_approval": False, "approval_status": "escalated_to_human"}

    def response_node(state: AgentState) -> dict:
        intent = state["intent"]

        if intent == "human":
            response = (
                "I’m connecting you with a human support specialist for a more "
                "detailed review of this issue."
            )
        elif intent == "unknown":
            response = (
                "I can only help with orders, shipments, returns, refunds, "
                "cancellations, and product policy questions. "
                "Please let me know if I can assist with any of those."
            )
        elif intent in POLICY_INTENTS and not state["retrieved_documents"]:
            # No RAG context — refuse to answer from training data.
            response = (
                "I don’t have documentation available to answer that question. "
                "Please contact our support team for more information."
            )
        else:
            intent_obj = type("_Intent", (), {
                "category": intent,
                "order_number": state["order_number"],
            })()
            response = generate_response(
                message=state["messages"][-1],
                intent=intent_obj,
                context=state["retrieved_documents"],
                tool_result=state["tool_result"],
                history=state.get("history", []),
                requires_approval=state.get("requires_approval", False),
            )
        return {"final_response": response}

    # ------------------------------------------------------------------ routing

    def route_after_classify(state: AgentState) -> str:
        intent = state["intent"]
        if intent in RETRIEVE_INTENTS:
            return "retrieve"
        if intent in TOOL_INTENTS:
            return "tool"
        if intent in ESCALATION_INTENTS:
            return "escalation"
        return "response"   # unknown → canned fallback

    def route_after_retrieve(state: AgentState) -> str:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            # If we have an order number, fetch its details before setting approval.
            return "tool" if state["order_number"] else "approval"
        # Pure policy intents (documentation) → respond directly.
        return "response"

    def route_after_tool(state: AgentState) -> str:
        return "approval" if state["intent"] in APPROVAL_INTENTS else "response"

    # ------------------------------------------------------------------ graph

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("approval", approval_node)
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
        {"tool": "tool", "approval": "approval", "response": "response"},
    )
    graph.add_conditional_edges(
        "tool", route_after_tool,
        {"approval": "approval", "response": "response"},
    )
    graph.add_edge("approval", "response")
    graph.add_edge("escalation", "response")
    graph.add_edge("response", END)
    return graph.compile()


def run_support_graph(
    db: Session,
    message: str,
    user_id: str,
    conversation_id: str,
    history: list[dict] | None = None,
) -> AgentState:
    graph = build_support_graph(db)
    return graph.invoke(
        {
            "messages": [message],
            "history": history or [],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "intent": None,
            "order_number": None,
            "retrieved_documents": [],
            "tool_result": None,
            "requires_approval": False,
            "approval_status": None,
            "final_response": None,
        }
    )