from pydantic import BaseModel, EmailStr

from app.models.users import UserRole


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class InviteCreateRequest(BaseModel):
    """Admin-only: create an agent invite."""
    name: str
    email: EmailStr


class InviteResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    invite_token: str

    class Config:
        from_attributes = True


class AcceptInviteRequest(BaseModel):
    invite_token: str
    password: str


class UserMeResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True
