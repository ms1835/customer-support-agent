from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.order_items import OrderItem
from app.models.orders import Order
from app.models.shipments import Shipment


def _order_number(order_number: str) -> int:
    try:
        return int(order_number.strip().lstrip("#"))
    except (TypeError, ValueError) as error:
        raise ValueError("The order number must be numeric.") from error


def get_order_details(db: Session, order_number: str) -> dict | None:
    order = db.scalar(
        select(Order)
        .where(Order.order_number == _order_number(order_number))
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        return None

    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "total_amount": str(order.total_amount),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
            }
            for item in order.items
        ],
    }


def get_order_status(db: Session, order_number: str) -> dict | None:
    order = db.scalar(
        select(Order).where(Order.order_number == _order_number(order_number))
    )
    if order is None:
        return None

    return {
        "order_number": order.order_number,
        "status": order.status.value,
    }


def get_shipment_status(db: Session, order_number: str) -> dict | None:
    order = db.scalar(
        select(Order).where(Order.order_number == _order_number(order_number))
    )
    if order is None:
        return None

    shipment = db.scalar(
        select(Shipment).where(Shipment.order_id == order.id)
    )
    if shipment is None:
        return None

    return {
        "order_number": order.order_number,
        "shipment_status": shipment.status.value,
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "estimated_delivery": (
            shipment.estimated_delivery.isoformat()
            if shipment.estimated_delivery
            else None
        ),
        "actual_delivery": (
            shipment.actual_delivery.isoformat() if shipment.actual_delivery else None
        ),
    }