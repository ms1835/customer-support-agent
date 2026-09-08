from app.models.shipments import Shipment
from sqlalchemy import select
from sqlalchemy.orm import Session

class ShipmentService:
    def __init__(self):
        pass

    def get_shipment_by_order_id(self, db: Session, order_id: int) -> Shipment | None:
        query = select(Shipment).where(
            Shipment.order_id == order_id
        )
        return db.scalar(query)