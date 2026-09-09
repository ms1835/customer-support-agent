from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.conversation_service import ConversationService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.refund_service import RefundService
from app.services.shipment_service import ShipmentService
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