from enum import Enum

from sqlalchemy import Column, Enum as SqlAlchemyEnum, Integer, String, ForeignKey, Numeric
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
    order_number = Column(Integer, unique=True, nullable=True, index=True)
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
    currency = Column(String(3), nullable=False, index=True)
    created_at = Column(String, index=True)
    updated_at = Column(String, index=True)

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )