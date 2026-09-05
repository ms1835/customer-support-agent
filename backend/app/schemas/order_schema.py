from datetime import datetime
from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from app.models.orders import OrderStatus


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: int
    user_id: int
    status: OrderStatus
    total_amount: Decimal
    currency: str
    created_At: datetime
    updated_At: datetime | None = None


class OrderCreateRequest(BaseModel):
    user_id: int
    total_amount: Decimal
    currency: str = "INR"


class CancelOrderRequest(BaseModel):
    order_id: int
    reason: str | None = None
