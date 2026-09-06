from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.database import Base

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    tracking_number = Column(String, index=True)
    carrier = Column(String, index=True)
    status = Column(String, index=True)
    estimated_delivery = Column(String, index=True)
    actual_delivery = Column(String, index=True)
