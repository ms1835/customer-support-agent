from typing import Literal

from pydantic import BaseModel, Field


class Intent(BaseModel):
    category: Literal[
        "documentation",
        "order",
        "shipment",
        "refund",
        "cancel",
        "human",
        "unknown",
    ] = Field(description="The singular lowercase support category.")
    order_number: str | None = Field(
        default=None,
        description="The order identifier exactly as written by the customer, or null.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the classification, from 0.0 to 1.0.",
    )