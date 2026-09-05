from pydantic import BaseModel, ConfigDict
from datetime import datetime

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    name: str
    email: str
    created_at: datetime
    updated_at: datetime | None = None
