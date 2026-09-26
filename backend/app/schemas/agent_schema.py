from pydantic import BaseModel
from typing import Literal


class ResumeRequest(BaseModel):
    decision: Literal["approve", "reject"]
