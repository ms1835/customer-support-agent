from app.models.shipments import Shipment
from app.models.orders import Order
from app.schemas.shipment_schema import ShipmentCreateRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

class ShipmentService:
    def __init__(self, db: Session):
        self.db = db

    def get_shipment_by_order_id(self, order_id: int) -> Shipment | None:
        query = select(Shipment).where(
            Shipment.order_id == order_id
        )
        return self.db.scalar(query)

    def create_shipment(
        self,
        order_id: int,
        shipment_data: ShipmentCreateRequest,
    ) -> Shipment:
        if self.db.get(Order, order_id) is None:
            raise ValueError("Order does not exist")
        if self.get_shipment_by_order_id(order_id) is not None:
            raise ValueError("A shipment already exists for this order")

        shipment = Shipment(order_id=order_id, **shipment_data.model_dump())
        try:
            self.db.add(shipment)
            self.db.commit()
            self.db.refresh(shipment)
            return shipment
        except Exception:
            self.db.rollback()
            raise