from order_service import get_order_by_id
from fastapi import APIRouter

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/{order_id}")
def get_order(order_id: int):
    order = get_order_by_id(order_id)
    if order is None:
        return {"error": "Order not found"}, 404
    return order