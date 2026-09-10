from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlAlchemyEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class RefundStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    REJECTED = "rejected"

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(precision=10, scale=2), nullable=False, index=True)
    status = Column(
        SqlAlchemyEnum(
            RefundStatus,
            name="refund_status",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=RefundStatus.PENDING,
        index=True,
    )
    reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True, index=True)

    order = relationship("Order", back_populates="refunds")