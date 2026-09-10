from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SqlAlchemyEnum, ForeignKey, Integer, String, func
from enum import Enum
from app.db.database import Base


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True)
    tracking_number = Column(String(100), nullable=True, index=True)
    carrier = Column(String(100), nullable=True, index=True)
    status = Column(
        SqlAlchemyEnum(
            ShipmentStatus,
            name="shipment_status",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=ShipmentStatus.PENDING,
        index=True,
    )
    estimated_delivery = Column(DateTime(timezone=True), nullable=True, index=True)
    actual_delivery = Column(DateTime(timezone=True), nullable=True, index=True)
