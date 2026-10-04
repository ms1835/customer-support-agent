from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.schemas.auth_schema import (
    AcceptInviteRequest,
    InviteCreateRequest,
    InviteResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserMeResponse,
)
from app.services.auth_service import (
    AuthService,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.users import User
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["Auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


# ── Helpers ──────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=False,   # set True in production behind HTTPS
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
    )


def _login_response(response: Response, user: User) -> TokenResponse:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Customer self-registration."""
    svc = AuthService(db)
    try:
        user = svc.register_customer(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _login_response(response, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    svc = AuthService(db)
    user = svc.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _login_response(response, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    # Accept token from cookie (browser) or body (API clients / mobile)
    cookie_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    body: RefreshRequest | None = None,
):
    token = cookie_token or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    svc = AuthService(db)
    try:
        access = svc.refresh_access_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Re-issue refresh cookie to extend session
    try:
        payload = decode_token(token)
        new_refresh = create_refresh_token(int(payload["sub"]))
        _set_refresh_cookie(response, new_refresh)
    except JWTError:
        pass

    return TokenResponse(access_token=access)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(_REFRESH_COOKIE)
    return {"detail": "Logged out"}


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(body: AcceptInviteRequest, response: Response, db: Session = Depends(get_db)):
    """Agent accepts invite and sets their password."""
    svc = AuthService(db)
    try:
        user = svc.accept_invite(body.invite_token, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _login_response(response, user)


@router.post("/invite", response_model=InviteResponse, status_code=201)
def create_invite(body: InviteCreateRequest, db: Session = Depends(get_db)):
    """
    Admin-only: create an agent invite.
    (Auth guard will be wired in Step 5 once get_current_user exists.)
    """
    svc = AuthService(db)
    try:
        user = svc.create_agent_invite(body.name, body.email)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return user
