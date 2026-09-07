from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from app.models.orders import OrderStatus


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: int
    user_id: int
    status: OrderStatus
    total_amount: Decimal
    items: list["OrderItemResponse"] = Field(default_factory=list)


class OrderItemCreateRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    currency: str
    created_at: str | None = None
    updated_at: str | None = None


class OrderCreateRequest(BaseModel):
    user_id: int
    items: list[OrderItemCreateRequest] = Field(min_length=1)
    currency: str = "INR"


class CancelOrderRequest(BaseModel):
    reason: str | None = None
