import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.users import AgentStatus, User, UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expire, "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------

class AuthService:

    def __init__(self, db: Session):
        self.db = db

    # ── Customer self-registration ──────────────────────────────────────────

    def register_customer(self, name: str, email: str, password: str) -> User:
        """Create a new customer account. Raises ValueError if email taken."""
        existing = self.db.scalar(select(User).where(User.email == email))
        if existing:
            raise ValueError("Email already registered")

        now = datetime.now(timezone.utc)
        user = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.CUSTOMER,
            is_active=True,
            created_at=now,
        )
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    # ── Login ───────────────────────────────────────────────────────────────

    def authenticate(self, email: str, password: str) -> User | None:
        """Return User if credentials are valid, else None."""
        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not user.is_active:
            return None
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            return None
        return user

    # ── Agent invite flow ───────────────────────────────────────────────────

    def create_agent_invite(self, name: str, email: str) -> User:
        """
        Admin creates a placeholder agent account with an invite token.
        The agent must call accept_invite() to set their password.
        Raises ValueError if email already exists.
        """
        existing = self.db.scalar(select(User).where(User.email == email))
        if existing:
            raise ValueError("Email already registered")

        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.INVITE_TOKEN_EXPIRE_HOURS)

        now = datetime.now(timezone.utc)
        user = User(
            name=name,
            email=email,
            role=UserRole.AGENT,
            is_active=False,          # not active until they accept invite
            agent_status=AgentStatus.OFFLINE,
            current_ticket_count=0,
            invite_token=token,
            invite_expires_at=expires,
            created_at=now,
        )
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def accept_invite(self, invite_token: str, password: str) -> User:
        """
        Agent sets their password via invite token, activating their account.
        Raises ValueError on invalid/expired token.
        """
        user = self.db.scalar(select(User).where(User.invite_token == invite_token))
        if not user:
            raise ValueError("Invalid invite token")
        if user.invite_expires_at and user.invite_expires_at < datetime.now(timezone.utc):
            raise ValueError("Invite token has expired")

        try:
            user.hashed_password = hash_password(password)
            user.is_active = True
            user.agent_status = AgentStatus.AVAILABLE
            user.invite_token = None
            user.invite_expires_at = None
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    # ── Token refresh ───────────────────────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> str:
        """Validate refresh token and issue a new access token."""
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise ValueError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        user_id = int(payload["sub"])
        user = self.db.get(User, user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        return create_access_token(user_id, user.role.value)
