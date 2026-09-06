from app.models.shipments import Shipment
from sqlalchemy.orm import Session

def get_shipment_by_order_id(db: Session, order_id: int) -> Shipment | None:
    query = select(Shipment).where(
        Shipment.order_id == order_id
    )
    return db.scalar(query)