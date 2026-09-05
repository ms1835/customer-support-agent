from app.models.users import User
from app.schemas.user_schema import UserCreateRequest
from sqlalchemy.orm import Session

def get_user_by_id(db: Session, user_id: int) -> User | None:
    query = select(User).where(User.id == user_id)
    return db.scalar(query)