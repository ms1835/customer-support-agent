from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(ge=0)
    weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    is_active: bool = Field(default=True)

class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str
    description: str | None
    price: Decimal
    stock_quantity: int
    weight_kg: Decimal | None
    is_active: bool