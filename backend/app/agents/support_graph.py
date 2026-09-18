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


class AgentState(TypedDict):
    messages: list
    user_id: str
    conversation_id: str
    intent: str | None
    order_number: str | None
    retrieved_documents: list
    tool_result: dict | None
    requires_approval: bool
    approval_status: str | None
    final_response: str | None


POLICY_INTENTS = {"documentation"}
APPROVAL_INTENTS = {"cancel", "cancellation", "refund"}
TOOL_INTENTS = {"order", "shipment"}
ESCALATION_INTENTS = {"human"}


def build_support_graph(db: Session):
    def classify_node(state: AgentState) -> dict:
        user_message = state["messages"][-1]
        intent = generate_intent(user_message)
        return {
            "intent": intent.category,
            "order_number": intent.order_number,
        }

    def retrieve_node(state: AgentState) -> dict:
        documents = retrieve_relevant_chunks(db, state["messages"][-1])
        return {"retrieved_documents": documents}

    def tool_node(state: AgentState) -> dict:
        intent = state["intent"]
        order_number = state["order_number"]
        if not order_number:
            return {
                "tool_result": {
                    "error": "Please provide your order number so I can look that up."
                }
            }

        try:
            if intent == "shipment":
                result = get_shipment_status(db, order_number)
            elif any(
                keyword in state["messages"][-1].lower()
                for keyword in ("status", "where", "track", "delivered")
            ):
                result = get_order_status(db, order_number)
            else:
                result = get_order_details(db, order_number)
        except ValueError as error:
            return {"tool_result": {"error": str(error)}}

        if result is None:
            result = {
                "error": f"No {intent} record was found for order number {order_number}."
            }
        return {"tool_result": result}

    def approval_node(state: AgentState) -> dict:
        intent = state["intent"]
        if intent in APPROVAL_INTENTS:
            return {
                "requires_approval": True,
                "approval_status": "pending",
            }

        return {
            "requires_approval": False,
            "approval_status": "not_required",
        }

    def escalation_node(state: AgentState) -> dict:
        return {
            "requires_approval": False,
            "approval_status": "escalated_to_human",
        }

    def response_node(state: AgentState) -> dict:
        intent = state["intent"]
        if intent == "human":
            response = (
                "I’m connecting you with a human support specialist for a more "
                "detailed review of this issue."
            )
        elif intent == "unknown":
            response = (
                "That question is outside my support scope. "
                "I can help with products, orders, shipments, refunds, "
                "and cancellations."
            )
        else:
            response = generate_response(
                state["messages"][-1],
                type("IntentResult", (), {
                    "category": intent,
                    "order_number": state["order_number"],
                })(),
                state["retrieved_documents"],
                state["tool_result"],
            )
        return {"final_response": response}

    def route_after_classify(state: AgentState) -> str:
        if state["intent"] in POLICY_INTENTS:
            return "retrieve"
        if state["intent"] in TOOL_INTENTS:
            return "tool"
        if state["intent"] in APPROVAL_INTENTS:
            return "approval"
        if state["intent"] in ESCALATION_INTENTS:
            return "escalation"
        return "approval"

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("approval", approval_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("response", response_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "retrieve": "retrieve",
            "tool": "tool",
            "approval": "approval",
            "escalation": "escalation",
        },
    )
    graph.add_edge("retrieve", "approval")
    graph.add_edge("tool", "approval")
    graph.add_edge("approval", "response")
    graph.add_edge("escalation", "response")
    graph.add_edge("response", END)
    return graph.compile()


def run_support_graph(
    db: Session,
    message: str,
    user_id: str,
    conversation_id: str,
) -> AgentState:
    graph = build_support_graph(db)
    return graph.invoke(
        {
            "messages": [message],
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