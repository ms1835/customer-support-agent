from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.users import User, UserRole
from app.services.agent_service import AgentService
from app.services.auth_service import decode_token
from app.services.conversation_service import ConversationService
from app.services.escalation_service import EscalationService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.refund_service import RefundService
from app.services.shipment_service import ShipmentService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the Bearer token; return the matching User."""
    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise _unauthorized
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise _unauthorized

    if payload.get("type") != "access":
        raise _unauthorized

    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise _unauthorized
    return user


def require_customer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.CUSTOMER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customers only")
    return current_user


def require_agent(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agents only")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(db)


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db)


def get_shipment_service(db: Session = Depends(get_db)) -> ShipmentService:
    return ShipmentService(db)


def get_refund_service(db: Session = Depends(get_db)) -> RefundService:
    return RefundService(db)


def get_conversation_service(
    db: Session = Depends(get_db),
) -> ConversationService:
    return ConversationService(db)


def get_escalation_service(db: Session = Depends(get_db)) -> EscalationService:
    return EscalationService(db)


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def get_agent_service(db: Session = Depends(get_db)) -> AgentService:
    return AgentService(db)