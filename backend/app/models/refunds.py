from sqlalchemy import Column, Integer, String, ForeignKey, Numeric
from app.db.database import Base

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(precision=10, scale=2), nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    reason = Column(String, index=True)
    created_at = Column(String, index=True)
    processed_at = Column(String, index=True)