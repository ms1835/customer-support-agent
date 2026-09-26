from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime


class AssistantResponse(BaseModel):
    response: str
    requires_approval: bool = False
    approval_status: str | None = None