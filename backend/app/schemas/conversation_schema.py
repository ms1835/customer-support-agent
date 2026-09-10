from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversations import ConversationStatus
from app.schemas.message_schema import MessageResponse


class ConversationCreateRequest(BaseModel):
    user_id: int = Field(gt=0)

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)