from pydantic import BaseModel, ConfigDict


class UserCreateRequest(BaseModel):
    name: str
    email: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: str | None = None
