import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

try:
    from langchain_aws import ChatBedrock
except ImportError:
    ChatBedrock = None

from app.config.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_MODEL_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_PROVIDER,
)
from app.schemas.intent_schema import Intent


def _build_llm(*, structured_output: bool = False):
    if LLM_PROVIDER == "aws":
        if ChatBedrock is None:
            raise ImportError("langchain-aws is required when LLM_PROVIDER=aws")
        llm = ChatBedrock(
            model=AWS_MODEL_ID,
            provider="amazon",
            region=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            model_kwargs={"temperature": 0},
        )
    else:
        llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0,
        )

    if structured_output:
        method = "json_mode" if LLM_PROVIDER == "aws" else "json_schema"
        return llm.with_structured_output(Intent, method=method)
    return llm


def _extract_order_number(message: str) -> str | None:
    match = re.search(r"#?(\d{3,})", message)
    return match.group(0).lstrip("#") if match else None


def infer_fallback_intent(message: str) -> Intent:
    text = message.lower()
    order_number = _extract_order_number(message)

    if re.search(r"\b(refund|refunded|money back|get my refund|refund status)\b", text):
        if any(keyword in text for keyword in [
            "how long",
            "how many days",
            "days",
            "time",
            "processing",
            "status",
            "eligibility",
            "policy",
            "when",
        ]):
            return Intent(category="documentation", order_number=order_number, confidence=0.0)
        return Intent(category="refund", order_number=order_number, confidence=0.0)

    if re.search(r"\b(cancel|cancellation|cancel my order)\b", text):
        return Intent(category="cancel", order_number=order_number, confidence=0.0)

    if re.search(r"\b(return|returned|return my order)\b", text):
        return Intent(category="return", order_number=order_number, confidence=0.0)

    if re.search(r"\b(shipment|tracking|track my order|delivered|where is my order)\b", text):
        return Intent(category="shipment", order_number=order_number, confidence=0.0)

    if re.search(r"\b(order|status of my order|where is my order|my order)\b", text):
        return Intent(category="order", order_number=order_number, confidence=0.0)

    if re.search(r"\b(agent|human|live person|speak to someone|escalate)\b", text):
        return Intent(category="human", order_number=order_number, confidence=0.0)

    return Intent(category="unknown", order_number=order_number, confidence=0.0)


def generate_intent(message: str, history: list[dict] | None = None) -> Intent:
    llm = _build_llm(structured_output=True)

    # Last 6 turns (3 exchanges) — enough for pronoun/reference resolution
    # without ballooning classifier token cost.
    recent = (history or [])[-6:]
    history_messages: list = []
    for turn in recent:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            history_messages.append(AIMessage(content=content))

    try:
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "Classify the customer support request using the Intent schema. "
                        "Return ONLY a valid JSON object — never a customer-facing reply.\n"
                        "Category must be exactly one of: "
                        "documentation, return, order, shipment, refund, cancel, human, unknown.\n"
                        "- Use 'documentation' for policy/FAQ questions (refund timelines, "
                        "return eligibility, warranty, payment methods, account security).\n"
                        "- Use 'return' when the customer wants to initiate a return.\n"
                        "- Use 'refund' when the customer wants a refund on an order.\n"
                        "- Use 'cancel' when the customer wants to cancel an order.\n"
                        "- Use 'order' for order status or details lookups.\n"
                        "- Use 'shipment' for tracking or delivery questions.\n"
                        "- Use 'human' when the customer asks to speak with a person.\n"
                        "- Use 'unknown' only when the request is completely unrelated to "
                        "e-commerce support (orders, shipments, returns, refunds, cancellations, "
                        "product policy). Do NOT use unknown for ambiguous follow-ups — "
                        "use conversation history to resolve them.\n"
                        "Use the conversation history to resolve pronouns and follow-up "
                        "references (e.g. 'it', 'that order', 'how long') in the current message.\n"
                        "order_number: extract from the current message exactly as written. "
                        "If the customer refers to a prior order without repeating its number, "
                        "extract it from the history. Set to null if no order number is present.\n"
                        "confidence: 0.0–1.0."
                    )
                ),
                *history_messages,
                HumanMessage(content=message),
            ]
        )
    except Exception as error:
        if getattr(error, "status_code", None) == 413:
            response = Intent(category="unknown", order_number=None, confidence=0.0)
        else:
            raise

    if response.category == "unknown" or response.confidence <= 0.15:
        fallback = infer_fallback_intent(message)
        if fallback.category != "unknown":
            response = fallback

    print(f"Intent classification response: {response}")
    return response


def generate_response(
    message: str,
    intent: Intent,
    context: list[dict[str, str]] | None = None,
    tool_result: dict | None = None,
    history: list[dict] | None = None,
    requires_approval: bool = False,
) -> str:
    llm = _build_llm()
    response_chain = llm | StrOutputParser()

    # Cap history to the last 20 turns (10 exchanges) to stay within token limits.
    recent_history = (history or [])[-20:]
    history_messages: list = []
    for turn in recent_history:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            history_messages.append(AIMessage(content=content))

    # Build the context block that accompanies the customer's message.
    context_parts: list[str] = []
    if context:
        docs = "\n\n".join(
            f"[{chunk['document_name']}]\n{chunk['content']}" for chunk in context
        )
        context_parts.append(f"Policy documentation:\n{docs}")

    if tool_result:
        error_key = tool_result.get("error", "")
        if error_key == "no_order_number":
            context_parts.append(
                "Tool result: The customer did not provide an order number."
            )
        elif isinstance(error_key, str) and error_key.endswith("_not_found"):
            order_id = error_key.replace("_not_found", "").replace("order_", "")
            context_parts.append(
                f"Tool result: No order found for order number {order_id}."
            )
        else:
            context_parts.append(
                f"Live order data:\n{json.dumps(tool_result, indent=2)}"
            )

    if not context_parts:
        context_parts.append("No context retrieved.")

    approval_note = (
        "\nIMPORTANT: This action (cancel/refund/return) requires human review before "
        "it is executed. Tell the customer their request has been received and is "
        "pending review — do NOT confirm it is completed or promise a specific outcome."
        if requires_approval else ""
    )

    system_prompt = (
        "You are a concise customer support assistant for an e-commerce company.\n"
        "Scope: only answer questions about orders, shipments, returns, refunds, "
        "cancellations, and product policy. For anything outside this scope, "
        "politely decline and redirect.\n"
        "Rules:\n"
        "- Never invent order details, tracking numbers, delivery dates, or policies.\n"
        "- For policy questions, answer strictly from the provided documentation; "
        "if the documentation does not cover it, say you don't have that information.\n"
        "- For order/shipment questions, answer from the live order data only.\n"
        "- Do not mention internal labels (intent category, tool names, etc.).\n"
        "- Do not claim an order was changed, cancelled, refunded, or shipped "
        "unless the live data confirms it."
        + approval_note
    )

    context_block = "\n\n".join(context_parts)

    response = response_chain.invoke(
        [
            SystemMessage(content=system_prompt),
            *history_messages,
            HumanMessage(
                content=(
                    f"{message}\n\n"
                    f"[Internal context — not visible to customer]\n"
                    f"Topic: {intent.category} | Order ref: {intent.order_number or 'none'}\n"
                    f"{context_block}"
                )
            ),
        ]
    )
    print(f"Assistant response: {response}")
    return response