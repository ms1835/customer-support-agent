from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentStatus


class AgentService:

    def __init__(self, db: Session):
        self.db = db

    def create_agent(self, name: str, email: str) -> Agent:
        try:
            agent = Agent(
                name=name,
                email=email,
                status=AgentStatus.AVAILABLE,
                current_ticket_count=0,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)
            return agent
        except Exception:
            self.db.rollback()
            raise

    def get_agent(self, agent_id: int) -> Agent | None:
        return self.db.get(Agent, agent_id)

    def list_agents(self) -> list[Agent]:
        return list(self.db.scalars(select(Agent).order_by(Agent.name)).all())

    def update_status(self, agent_id: int, status: AgentStatus) -> Agent | None:
        agent = self.db.get(Agent, agent_id)
        if agent is None:
            return None
        try:
            agent.status = status
            self.db.commit()
            self.db.refresh(agent)
            return agent
        except Exception:
            self.db.rollback()
            raise
