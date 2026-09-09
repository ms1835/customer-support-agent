from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_product_service
from app.schemas.product_schema import ProductCreateRequest, ProductResponse
from app.services.product_service import ProductService


router = APIRouter(prefix="/api/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    product_data: ProductCreateRequest,
    service: ProductService = Depends(get_product_service),
):
    try:
        return service.create_product(product_data)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
):
    product = service.get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product