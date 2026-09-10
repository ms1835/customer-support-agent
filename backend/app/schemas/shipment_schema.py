from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.models.shipments import ShipmentStatus


class ShipmentCreateRequest(BaseModel):
    tracking_number: str | None = None
    carrier: str
    estimated_delivery: datetime | None = None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    tracking_number: str
    carrier: str
    status: ShipmentStatus
    estimated_delivery: datetime | None = None
    actual_delivery: datetime | None = None
