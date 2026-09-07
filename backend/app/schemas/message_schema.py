from pydantic import BaseModel, ConfigDict, Field

from app.models.messages import MessageRole


class MessageCreateRequest(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: MessageRole
    content: str
    created_at: str | None = None