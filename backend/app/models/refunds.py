from sqlalchemy import Column, Integer, String
from database import Base

def Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, foreign_key="orders.id", index=True)
    amount = Column(Integer, index=True)
    status = Column(String, index=True)
    reason = Column(String, index=True)
    created_at = Column(String, index=True)
    processed_at = Column(String, index=True)