from sqlalchemy import Column, Integer, String
from database import Base

def OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, foreign_key="orders.id", index=True)
    product_id = Column(Integer, foreign_key="products.id", index=True)
    quantity = Column(Integer, index=True)
    unit_price = Column(Integer, index=True)