from app.services.order_service import get_order_by_id
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.order_schema import OrderResponse, OrderCreateRequest
from app.services.order_service import create_order, get_order_by_id
from app.db.database import get_db

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
):
    order = get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.get("/{order_id}/shipment", response_model=ShipmentResponse)
def get_order_shipment(
    order_id: int,
    db: Session = Depends(get_db)
):
    response = shipment_service.get_shipment_by_order_id(db, order_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return response


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    request: CancelOrderRequest,
    db: Session = Depends(get_db),
):
    response = order_service.cancel_order(db, order_id, request.reason)
    if response is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return response

@router.post("/{order_id}/refund", response_model=RefundResponse, status_code=201)
def refund_order(
    order_id: int,
    request: RefundCreateRequest,
    db: Session = Depends(get_db),
):
    response = refund_service.create_refund(db, order_id, request)

    if response is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return response

@router.post("/", response_model=OrderResponse, status_code=201)
def create_new_order(
    order_data: OrderCreateRequest,
    db: Session = Depends(get_db),
):
    order = create_order(db, order_data)
    return order
