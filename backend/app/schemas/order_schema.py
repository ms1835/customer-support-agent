from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.orders import OrderStatus, PaymentMethod


def _normalize_enum_input(value):
    """Accept display-style input such as 'Credit Card' or 'Processing'."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


class ShippingAddress(BaseModel):
    street: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=1, max_length=100)


class OrderItemCreateRequest(BaseModel):
    # price_per_unit sent by a client is ignored; prices come from the product table.
    product_code: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_code: str
    quantity: int
    price_per_unit: Decimal = Field(validation_alias="unit_price")


class OrderCreateRequest(BaseModel):
    user_id: int = Field(gt=0)
    status: OrderStatus = OrderStatus.PENDING
    shipping_address: ShippingAddress
    payment_method: PaymentMethod
    items: list[OrderItemCreateRequest] = Field(min_length=1)

    @field_validator("status", "payment_method", mode="before")
    @classmethod
    def _normalize_enums(cls, value):
        return _normalize_enum_input(value)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    order_date: datetime = Field(validation_alias="created_at")
    status: OrderStatus
    shipping_address: ShippingAddress
    payment_method: str
    total_amount: Decimal
    items: list[OrderItemResponse] = Field(default_factory=list)


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)