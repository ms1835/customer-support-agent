from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.order_items import OrderItem
from app.models.orders import Order
from app.models.shipments import Shipment


def _parse_order_id(order_ref: str) -> int:
    """Parse the order ID from a customer-provided string (e.g. '#123' → 123)."""
    try:
        return int(order_ref.strip().lstrip("#"))
    except (TypeError, ValueError) as error:
        raise ValueError("The order ID must be numeric.") from error


def get_order_details(db: Session, order_number: str) -> dict | None:
    order = db.scalar(
        select(Order)
        .where(Order.id == _parse_order_id(order_number))
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    if order is None:
        return None

    return {
        "order_number": order.id,
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
        select(Order).where(Order.id == _parse_order_id(order_number))
    )
    if order is None:
        return None

    return {
        "order_number": order.id,
        "status": order.status.value,
    }


def get_shipment_status(db: Session, order_number: str) -> dict | None:
    order = db.scalar(
        select(Order).where(Order.id == _parse_order_id(order_number))
    )
    if order is None:
        return None  # order itself not found

    shipment = db.scalar(
        select(Shipment).where(Shipment.order_id == order.id)
    )
    if shipment is None:
        # Order exists but has not been shipped yet — return informative state
        # rather than None so the LLM can give a meaningful answer.
        return {
            "order_number": order.id,
            "order_status": order.status.value,
            "shipment_status": "not_shipped",
            "message": "This order has not been shipped yet.",
        }

    return {
        "order_number": order.id,
        "order_status": order.status.value,
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