from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from app.config.settings import GROQ_API_KEY, GROQ_MODEL


def generate_reply(message: str) -> str:
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0,
    )

    response = llm.invoke(
        [
            SystemMessage(
                content="You are a concise and helpful customer support assistant."
            ),
            HumanMessage(content=message),
        ]
    )
    return response.content if isinstance(response.content, str) else str(response.content)