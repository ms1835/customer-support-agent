from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.users import User, UserRole
from app.models.messages import Message, MessageRole
from app.models.support_tickets import SupportTicket, TicketPriority, TicketStatus


class TicketService:

    def __init__(self, db: Session):
        self.db = db

    def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        return self.db.get(SupportTicket, ticket_id)

    def get_ticket_by_conversation(self, conversation_id: int) -> SupportTicket | None:
        return self.db.scalar(
            select(SupportTicket).where(SupportTicket.conversation_id == conversation_id)
        )

    def list_tickets(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        agent_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SupportTicket]:
        query = select(SupportTicket).order_by(SupportTicket.created_at.desc())
        if status is not None:
            query = query.where(SupportTicket.status == status)
        if priority is not None:
            query = query.where(SupportTicket.priority == priority)
        if agent_id is not None:
            query = query.where(SupportTicket.assigned_agent_id == agent_id)
        query = query.limit(limit).offset(offset)
        return list(self.db.scalars(query).all())

    def assign_ticket(self, ticket_id: int, agent_id: int) -> SupportTicket | None:
        """
        Assign or reassign a ticket to a specific agent.
        Decrements the previous agent's load counter and increments the new one.
        """
        ticket = self.db.get(SupportTicket, ticket_id)
        new_agent = self.db.get(User, agent_id)
        if ticket is None or new_agent is None or new_agent.role != UserRole.AGENT:
            return None

        try:
            # Release previous agent's load if reassigning.
            if ticket.assigned_agent_id and ticket.assigned_agent_id != agent_id:
                prev_agent = self.db.get(User, ticket.assigned_agent_id)
                if prev_agent and prev_agent.current_ticket_count > 0:
                    prev_agent.current_ticket_count -= 1

            ticket.assigned_agent_id = agent_id
            ticket.status = TicketStatus.ASSIGNED
            ticket.updated_at = datetime.now(timezone.utc)
            new_agent.current_ticket_count += 1

            self.db.commit()
            self.db.refresh(ticket)
            return ticket
        except Exception:
            self.db.rollback()
            raise

    def add_agent_message(
        self,
        ticket_id: int,
        agent_id: int,
        content: str,
    ) -> Message | None:
        """
        Human agent posts a reply into the escalated conversation.
        Advances ticket status to IN_PROGRESS on first reply.
        """
        ticket = self.db.get(SupportTicket, ticket_id)
        if ticket is None:
            return None
        if ticket.assigned_agent_id != agent_id:
            raise ValueError("Agent is not assigned to this ticket")

        try:
            message = Message(
                conversation_id=ticket.conversation_id,
                role=MessageRole.AGENT,
                content=content,
                created_at=datetime.now(timezone.utc),
            )
            if ticket.status == TicketStatus.ASSIGNED:
                ticket.status = TicketStatus.IN_PROGRESS
            ticket.updated_at = datetime.now(timezone.utc)
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except Exception:
            self.db.rollback()
            raise

    def update_notes(self, ticket_id: int, notes: str) -> SupportTicket | None:
        ticket = self.db.get(SupportTicket, ticket_id)
        if ticket is None:
            return None
        try:
            ticket.notes = notes
            ticket.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(ticket)
            return ticket
        except Exception:
            self.db.rollback()
            raise

    def resolve_ticket(
        self,
        ticket_id: int,
        notes: str | None = None,
    ) -> SupportTicket | None:
        """Thin wrapper — delegates to EscalationService for full lifecycle close."""
        from app.services.escalation_service import EscalationService
        return EscalationService(self.db).resolve_ticket(ticket_id, notes)
