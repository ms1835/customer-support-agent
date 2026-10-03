from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService
from app.services.escalation_service import EscalationService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.refund_service import RefundService
from app.services.shipment_service import ShipmentService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService


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