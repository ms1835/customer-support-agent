from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.refunds import RefundStatus

class RefundCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reason: str | None = Field(default=None, max_length=500)

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    amount: Decimal
    reason: str | None = None
    status: RefundStatus
    created_at: datetime
    processed_at: datetime | None = None