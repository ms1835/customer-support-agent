from datetime import datetime, timezone

from app.models.users import User
from app.schemas.user_schema import UserCreateRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        query = select(User).where(User.id == user_id)
        return self.db.scalar(query)

    def create_user(self, user_data: UserCreateRequest) -> User:
        existing_user = self.db.scalar(
            select(User).where(User.email == user_data.email)
        )
        if existing_user is not None:
            raise ValueError("A user with this email already exists")

        user = User(
            name=user_data.name,
            email=user_data.email,
            created_at=datetime.now(timezone.utc),
        )
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise