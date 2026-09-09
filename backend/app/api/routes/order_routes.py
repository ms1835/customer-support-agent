from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_order_service,
    get_refund_service,
    get_shipment_service,
)
from app.schemas.order_schema import OrderResponse, OrderCreateRequest, CancelOrderRequest
from app.services.order_service import OrderService
from app.services.refund_service import RefundService
from app.services.shipment_service import ShipmentService
from app.schemas.shipment_schema import ShipmentCreateRequest, ShipmentResponse
from app.schemas.refund_schema import RefundResponse, RefundCreateRequest

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/{order_id}/shipment", response_model=ShipmentResponse)
def get_order_shipment(
    order_id: int,
    service: ShipmentService = Depends(get_shipment_service),
):
    response = service.get_shipment_by_order_id(order_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return response


@router.post(
    "/{order_id}/shipment",
    response_model=ShipmentResponse,
    status_code=201,
)
def create_order_shipment(
    order_id: int,
    shipment_data: ShipmentCreateRequest,
    service: ShipmentService = Depends(get_shipment_service),
):
    try:
        return service.create_shipment(order_id, shipment_data)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    request: CancelOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        response = service.cancel_order(order_id, request.reason)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if response is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return response

@router.post("/{order_id}/refund", response_model=RefundResponse, status_code=201)
def refund_order(
    order_id: int,
    request: RefundCreateRequest,
    service: RefundService = Depends(get_refund_service),
):
    try:
        response = service.create_refund(order_id, request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    if response is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return response

@router.post("/", response_model=OrderResponse, status_code=201)
def create_new_order(
    order_data: OrderCreateRequest,
    service: OrderService = Depends(get_order_service),
):
    try:
        order = service.create_order(order_data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return order


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
):
    order = service.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
