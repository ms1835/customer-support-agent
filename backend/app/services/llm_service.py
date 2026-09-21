import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

try:
    from langchain_aws import ChatBedrock
except ImportError:  # pragma: no cover - dependency is optional until installed
    ChatBedrock = None

from app.config.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_MODEL_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    AWS_SESSION_TOKEN,
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
            model_id=AWS_MODEL_ID,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN,
            model_kwargs={"temperature": 0},
        )
    else:
        llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0,
        )

    if structured_output:
        return llm.with_structured_output(Intent, method="json_schema")
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


def generate_intent(message: str) -> Intent:
    llm = _build_llm(structured_output=True)

    try:
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "Classify the customer request using the Intent schema. "
                        "Return only a valid JSON object matching the Intent schema; "
                        "never return a customer-facing reply. "
                        "The category must be exactly one of these lowercase values: "
                        "documentation, return, order, shipment, refund, cancel, cancellation, human, unknown. "
                        "Use unknown for requests unrelated to customer support, orders, "
                        "shipments, returns, refunds, cancellations, or product documentation. "
                        "Use singular return, order, shipment, refund, cancel, and cancellation values; "
                        "do not use plural forms such as orders or shipments. "
                        "Set order_number to the identifier exactly as written, or null "
                        "when none is present. Set confidence to a number from 0.0 to 1.0."
                    )
                ),
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
) -> str:
    llm = _build_llm()
    response_chain = llm | StrOutputParser()
    context_text = "\n\n".join(
        f"Source: {chunk['document_name']}\n{chunk['content']}" for chunk in (context or [])
    )
    response = response_chain.invoke(
        [
            SystemMessage(
                content=(
                    "You are a concise customer support assistant. "
                    "Respond naturally to the customer. The intent classification "
                    "is internal context only; do not mention it or claim that an "
                    "order was changed, cancelled, refunded, or tracked. "
                    "For policy and documentation questions, answer using the provided context. "
                    "For operational questions, answer using the tool result. "
                    "Never invent order, shipment, tracking, or delivery details. "
                    "If the context does not contain the answer, say that you do not "
                    "have that information instead of inventing a policy."
                )
            ),
            HumanMessage(
                content=(
                    f"Customer message: {message}\n"
                    f"Internal category: {intent.category}\n"
                    f"Order number: {intent.order_number}\n"
                    f"Documentation context:\n{context_text or 'No relevant documentation was found.'}"
                    f"\nTool result:\n{json.dumps(tool_result) if tool_result else 'No tool was called.'}"
                )
            ),
        ]
    )
    print(f"Assistant response: {response}")
    return response