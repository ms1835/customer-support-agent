from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from database import Base

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    quantity = Column(Integer, index=True)
    unit_price = Column(Numeric(precision=10, scale=2), index=True)