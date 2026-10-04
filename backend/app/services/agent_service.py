from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.users import AgentStatus, User, UserRole


class AgentService:

    def __init__(self, db: Session):
        self.db = db

    def get_agent(self, agent_id: int) -> User | None:
        user = self.db.get(User, agent_id)
        if user and user.role == UserRole.AGENT:
            return user
        return None

    def list_agents(self) -> list[User]:
        return list(
            self.db.scalars(
                select(User).where(User.role == UserRole.AGENT).order_by(User.name)
            ).all()
        )

    def update_status(self, agent_id: int, status: AgentStatus) -> User | None:
        agent = self.get_agent(agent_id)
        if agent is None:
            return None
        try:
            agent.agent_status = status
            self.db.commit()
            self.db.refresh(agent)
            return agent
        except Exception:
            self.db.rollback()
            raise
