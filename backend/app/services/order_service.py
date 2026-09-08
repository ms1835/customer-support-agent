from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order_items import OrderItem
from app.models.orders import Order, OrderStatus
from app.models.products import Product
from app.models.users import User
from app.schemas.order_schema import OrderCreateRequest

class OrderService:

    def __init__(self):
        pass

    def get_order_by_id(self, db: Session, order_id: int) -> Order | None:
        query = select(Order).where(Order.id == order_id)
        return db.scalar(query)

    def create_order(self, db: Session, order_data: OrderCreateRequest) -> Order:
        if db.scalar(select(User).where(User.id == order_data.user_id)) is None:
            raise ValueError("User does not exist")

        product_ids = [item.product_id for item in order_data.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product may appear only once in an order")

        products = db.scalars(
            select(Product)
            .where(Product.id.in_(product_ids), Product.is_active.is_(True))
            .with_for_update()
        ).all()
        products_by_id = {product.id: product for product in products}
        missing_ids = set(product_ids) - products_by_id.keys()
        if missing_ids:
            raise ValueError(f"Active product(s) not found: {sorted(missing_ids)}")

        if any(product.currency != order_data.currency for product in products):
            raise ValueError("All products must use the order currency")

        total_amount = sum(
            (products_by_id[item.product_id].price * item.quantity for item in order_data.items),
            Decimal("0.00"),
        )
        order = Order(
            user_id=order_data.user_id,
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            currency=order_data.currency,
        )
        order.items = [
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=products_by_id[item.product_id].price,
            )
            for item in order_data.items
        ]

        try:
            db.add(order)
            db.flush()
            order.order_number = order.id
            db.commit()
            db.refresh(order)
            return order
        except Exception:
            db.rollback()
            raise


    def cancel_order(
        self,
        db: Session,
        order_id: int,
        reason: str | None = None,
    ) -> Order | None:
        order = db.get(Order, order_id)
        if order is None:
            return None
        if order.status in {OrderStatus.CANCELLED, OrderStatus.REFUNDED}:
            raise ValueError("Order cannot be cancelled in its current state")

        order.status = OrderStatus.CANCELLED
        db.commit()
        db.refresh(order)
        return order

    