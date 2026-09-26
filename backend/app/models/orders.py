from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlAlchemyEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(
        SqlAlchemyEnum(
            OrderStatus,
            name="order_status",
            create_constraint=True,
            validate_strings=True,
        ),
        index=True,
        nullable=False,
        default=OrderStatus.PENDING,
    )
    total_amount = Column(Numeric(precision=10, scale=2), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    refunds = relationship("Refund", back_populates="order")