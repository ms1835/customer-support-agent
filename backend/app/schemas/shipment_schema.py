from pydantic import BaseModel, ConfigDict


class ShipmentCreateRequest(BaseModel):
    tracking_number: str
    carrier: str
    status: str = "pending"
    estimated_delivery: str | None = None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    tracking_number: str
    carrier: str
    status: str
    estimated_delivery: str | None = None
    actual_delivery: str | None = None
