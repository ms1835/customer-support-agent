from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.products import Product
from app.schemas.product_schema import ProductCreateRequest


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def create_product(
        self,
        product_data: ProductCreateRequest,
    ) -> Product:
        existing_product = self.db.scalar(
            select(Product).where(Product.sku == product_data.sku)
        )
        if existing_product is not None:
            raise ValueError("A product with this SKU already exists")

        product = Product(**product_data.model_dump())
        try:
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            return product
        except Exception:
            self.db.rollback()
            raise

    def get_product_by_id(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)