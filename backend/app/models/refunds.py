from sqlalchemy import Column, Integer, String, ForeignKey, Numeric
from database import Base

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    amount = Column(Numeric(precision=10, scale=2), index=True)
    status = Column(String, index=True)
    reason = Column(String, index=True)
    created_at = Column(String, index=True)
    processed_at = Column(String, index=True)