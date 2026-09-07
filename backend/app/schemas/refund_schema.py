from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class RefundCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str | None = None

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    amount: Decimal
    reason: str | None = None
    status: str