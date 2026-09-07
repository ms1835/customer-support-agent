from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message_schema import MessageResponse


class ConversationCreateRequest(BaseModel):
    user_id: int
    status: str = "open"

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[MessageResponse] = Field(default_factory=list)