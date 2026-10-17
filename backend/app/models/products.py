from sqlalchemy import Boolean, Column, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    price = Column(Numeric(precision=10, scale=2), nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    weight_kg = Column(Numeric(precision=10, scale=2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    order_items = relationship("OrderItem", back_populates="product")