from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from app.models.orders import OrderStatus


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
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


class OrderCreateRequest(BaseModel):
    user_id: int = Field(gt=0)
    items: list[OrderItemCreateRequest] = Field(min_length=1)


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
