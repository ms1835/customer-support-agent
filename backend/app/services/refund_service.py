from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orders import Order
from app.models.refunds import Refund
from app.schemas.refund_schema import RefundCreateRequest

class RefundService:
    def __init__(self):
        pass

    def create_refund(
        self,
        db: Session,
        order_id: int,
        refund_data: RefundCreateRequest,
    ) -> Refund | None:
        order = db.scalar(select(Order).where(Order.id == order_id))
        if order is None:
            return None
        if order.status in {"cancelled", "refunded"}:
            raise ValueError("Cancelled or already refunded orders cannot be refunded")

        refunded_amount = db.scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.order_id == order_id,
                Refund.status.in_(["pending", "processed"]),
            )
        )
        if Decimal(str(refunded_amount)) + refund_data.amount > order.total_amount:
            raise ValueError("Refund amount exceeds the remaining refundable amount")

        refund = Refund(
            order_id=order_id,
            amount=refund_data.amount,
            reason=refund_data.reason,
            status="pending",
        )
        try:
            db.add(refund)
            db.commit()
            db.refresh(refund)
            return refund
        except Exception:
            db.rollback()
            raise