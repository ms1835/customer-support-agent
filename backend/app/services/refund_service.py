from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orders import Order, OrderStatus
from app.models.refunds import Refund, RefundStatus
from app.schemas.refund_schema import RefundCreateRequest

class RefundService:
    def __init__(self, db: Session):
        self.db = db

    def create_refund(
        self,
        order_id: int,
        refund_data: RefundCreateRequest,
    ) -> Refund | None:
        order = self.db.scalar(select(Order).where(Order.id == order_id))
        if order is None:
            return None
        if order.status in {OrderStatus.CANCELLED, OrderStatus.REFUNDED}:
            raise ValueError("Cancelled or already refunded orders cannot be refunded")

        refunded_amount = self.db.scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.order_id == order_id,
                Refund.status.in_([RefundStatus.PENDING, RefundStatus.PROCESSED]),
            )
        )
        if Decimal(str(refunded_amount)) + refund_data.amount > order.total_amount:
            raise ValueError("Refund amount exceeds the remaining refundable amount")

        refund = Refund(
            order_id=order_id,
            amount=refund_data.amount,
            reason=refund_data.reason,
            status=RefundStatus.PENDING,
        )
        try:
            self.db.add(refund)
            self.db.commit()
            self.db.refresh(refund)
            return refund
        except Exception:
            self.db.rollback()
            raise