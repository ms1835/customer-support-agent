from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orders import Order
from app.schemas.order_schema import OrderCreateRequest

def get_order_by_id(db:Session, order_id: int) -> Order | None:
    query = select(Order).where(Order.id == order_id)
    return db.scalar(query)

    # Placeholder function to simulate fetching an order from a database
    # In a real application, this would query the database for the order
    mock_orders = {
        1: {"id": 1, "item": "Laptop", "quantity": 1},
        2: {"id": 2, "item": "Smartphone", "quantity": 2},
    }
    return mock_orders.get(order_id)

def create_order(db: Session, order_data: OrderCreateRequest) -> Order:
    order = Order(
        user_id=order.user_id,
        total_amount=order_data.total_amount,
        currency=order_data.currency
    )

    db.add(order)
    db.commit()
    db.refresh(order)
    return order

    