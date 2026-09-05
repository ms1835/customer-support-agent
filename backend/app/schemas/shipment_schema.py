from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    shipment_id: int
    order_id: int
    tracking_number: str
    carrier: str
    status: str
    estimated_delivery: datetime | None = None
    actual_delivery: datetime | None = None
