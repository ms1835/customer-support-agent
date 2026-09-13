from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

from app.config.settings import GROQ_API_KEY, GROQ_MODEL
from app.schemas.intent_schema import Intent

def generate_intent(message: str) -> Intent:
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
    ).with_structured_output(Intent, method="json_mode")

    try:
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "Classify the customer request using the Intent schema. "
                        "Return only a valid JSON object matching the Intent schema; "
                        "never return a customer-facing reply. "
                        "The category must be exactly one of these lowercase values: "
                        "documentation, order, shipment, refund, cancel, human, unknown. "
                        "Use unknown for requests unrelated to customer support, orders, "
                        "shipments, refunds, cancellations, or product documentation. "
                        "Use singular order, shipment, refund, and cancel values; do not "
                        "use plural forms such as orders or shipments. "
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
    print(f"Intent classification response: {response}")
    return response


def generate_response(message: str, intent: Intent) -> str:
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
    )
    response_chain = llm | StrOutputParser()
    response = response_chain.invoke(
        [
            SystemMessage(
                content=(
                    "You are a concise customer support assistant. "
                    "Respond naturally to the customer. The intent classification "
                    "is internal context only; do not mention it or claim that an "
                    "order was changed, cancelled, refunded, or tracked."
                )
            ),
            HumanMessage(
                content=(
                    f"Customer message: {message}\n"
                    f"Internal category: {intent.category}\n"
                    f"Order number: {intent.order_number}"
                )
            ),
        ]
    )
    print(f"Assistant response: {response}")
    return response