from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class RefundCreateRequest(BaseModel):
    amount: Decimal
    reason: str | None = None

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    refund_id: int
    order_id: int
    amount: Decimal
    reason: str | None = None
    status: str