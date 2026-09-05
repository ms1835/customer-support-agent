from pydantic import BaseModel, ConfigDict

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conversation_id: int
    user_id: int
    agent_id: int | None = None
    status: str
    created_at: str
    updated_at: str | None = None