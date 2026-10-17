from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order_items import OrderItem
from app.models.orders import Order, OrderStatus
from app.models.products import Product
from app.models.users import User
from app.schemas.order_schema import OrderCreateRequest
from datetime import datetime, timezone

_CREATABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING}


class OrderService:

    def __init__(self, db: Session):
        self.db = db

    def get_order_by_id(self, order_id: int) -> Order | None:
        query = select(Order).where(Order.id == order_id)
        return self.db.scalar(query)

    def create_order(self, order_data: OrderCreateRequest) -> Order:
        if self.db.scalar(select(User).where(User.id == order_data.user_id)) is None:
            raise ValueError("User does not exist")

        product_codes = [item.product_code for item in order_data.items]
        if len(product_codes) != len(set(product_codes)):
            raise ValueError("Each product may appear only once in an order")

        products = self.db.scalars(
            select(Product)
            .where(Product.sku.in_(product_codes), Product.is_active.is_(True))
            .with_for_update()
        ).all()
        products_by_code = {product.sku: product for product in products}
        missing_codes = set(product_codes) - products_by_code.keys()
        if missing_codes:
            raise ValueError(f"Active product(s) not found: {sorted(missing_codes)}")

        total_amount = sum(
            (products_by_code[item.product_code].price * item.quantity for item in order_data.items),
            Decimal("0.00"),
        )
        if order_data.status not in _CREATABLE_STATUSES:
            raise ValueError(
                "A new order can only be created as: "
                + ", ".join(s.value for s in sorted(_CREATABLE_STATUSES, key=lambda s: s.value))
            )

        order = Order(
            user_id=order_data.user_id,
            status=order_data.status,
            payment_method=order_data.payment_method.value,
            shipping_address=order_data.shipping_address.model_dump(),
            total_amount=total_amount,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        order.items = [
            OrderItem(
                product_code=item.product_code,
                quantity=item.quantity,
                unit_price=products_by_code[item.product_code].price,
            )
            for item in order_data.items
        ]

        try:
            self.db.add(order)
            self.db.commit()
            self.db.refresh(order)
            return order
        except Exception:
            self.db.rollback()
            raise

    def cancel_order(
        self,
        order_id: int,
        reason: str | None = None,
    ) -> Order | None:
        order = self.db.get(Order, order_id)
        if order is None:
            return None
        if order.status in {OrderStatus.CANCELLED, OrderStatus.REFUNDED}:
            raise ValueError("Order cannot be cancelled in its current state")

        order.status = OrderStatus.CANCELLED
        self.db.commit()
        self.db.refresh(order)
        return order


    