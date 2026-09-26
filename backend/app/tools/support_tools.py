from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.order_items import OrderItem
from app.models.orders import Order, OrderStatus
from app.models.refunds import Refund, RefundStatus
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


# ---------------------------------------------------------------------------
# Action tools — executed AFTER human approval
# ---------------------------------------------------------------------------

def cancel_order_action(db: Session, order_number: str) -> dict:
    """Cancel an order. Called after human approval."""
    order_id = _parse_order_id(order_number)
    order = db.get(Order, order_id)
    if order is None:
        return {"error": f"order_{order_number}_not_found"}
    if order.status in {OrderStatus.CANCELLED, OrderStatus.REFUNDED}:
        return {"error": f"order_already_{order.status.value}"}
    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    print(f"[cancel_order_action] Order {order_id} cancelled.")
    return {"action": "cancelled", "order_number": order.id, "status": order.status.value}


def refund_order_action(db: Session, order_number: str) -> dict:
    """Create a refund record and mark the order refunded. Called after human approval."""
    order_id = _parse_order_id(order_number)
    order = db.get(Order, order_id)
    if order is None:
        return {"error": f"order_{order_number}_not_found"}
    if order.status == OrderStatus.REFUNDED:
        return {"error": "order_already_refunded"}
    refund = Refund(
        order_id=order.id,
        amount=order.total_amount,
        status=RefundStatus.PENDING,
        reason="Customer requested refund via support chat",
    )
    order.status = OrderStatus.REFUNDED
    db.add(refund)
    db.commit()
    db.refresh(order)
    print(f"[refund_order_action] Order {order_id} refunded — amount {order.total_amount}.")
    return {
        "action": "refunded",
        "order_number": order.id,
        "status": order.status.value,
        "refund_amount": str(order.total_amount),
    }


def initiate_return_action(db: Session, order_number: str) -> dict:
    """Initiate a return (creates a pending refund record). Called after human approval."""
    order_id = _parse_order_id(order_number)
    order = db.get(Order, order_id)
    if order is None:
        return {"error": f"order_{order_number}_not_found"}
    if order.status != OrderStatus.DELIVERED:
        return {"error": f"return_not_eligible_status_{order.status.value}"}
    refund = Refund(
        order_id=order.id,
        amount=order.total_amount,
        status=RefundStatus.PENDING,
        reason="Customer initiated return via support chat",
    )
    db.add(refund)
    db.commit()
    print(f"[initiate_return_action] Return initiated for order {order_id}.")
    return {
        "action": "return_initiated",
        "order_number": order.id,
        "status": order.status.value,
        "return_amount": str(order.total_amount),
    }