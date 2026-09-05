from enum import Enum

from sqlalchemy import Column, Enum as SqlAlchemyEnum, Integer, String, ForeignKey, Numeric
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

    order_id = Column(Integer, primary_key=True, index=True)
    order_number = Column(Integer, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
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
    total_amount = Column(Numeric(precision=10, scale=2), index=True)
    currency = Column(String, index=True)
    created_at = Column(String, index=True)
    updated_at = Column(String, index=True)