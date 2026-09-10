from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    price: Decimal
    is_active: bool