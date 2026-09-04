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

@router.post("/", response_model=OrderResponse, status_code=201)
def create_new_order(
    order_data: OrderCreateRequest,
    db: Session = Depends(get_db),
):
    order = create_order(db, order_data)
    return order
