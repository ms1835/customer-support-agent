from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Intent(BaseModel):
    category: Literal[
        "documentation",
        "return",
        "order",
        "shipment",
        "cancel",
        "refund",
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

    @field_validator("order_number", mode="before")
    @classmethod
    def normalise_null_string(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in ("null", "none", ""):
            return None
        return v