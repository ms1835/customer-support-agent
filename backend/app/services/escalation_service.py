from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.users import AgentStatus, User, UserRole
from app.models.conversations import Conversation, ConversationStatus
from app.models.support_tickets import EscalationType, SupportTicket, TicketPriority, TicketStatus


class EscalationService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def escalate_conversation(
        self,
        conversation_id: int,
        reason: str,
        escalation_type: EscalationType = EscalationType.USER_REQUESTED,
        priority: TicketPriority = TicketPriority.MEDIUM,
    ) -> SupportTicket:
        """
        Mark a conversation as escalated and create a support ticket.
        Idempotent: if the conversation is already escalated, returns the
        existing ticket without creating a duplicate.
        """
        conversation = self.db.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Already escalated — return existing ticket (idempotent).
        if conversation.status == ConversationStatus.ESCALATED and conversation.ticket:
            return conversation.ticket

        try:
            ticket = SupportTicket(
                conversation_id=conversation_id,
                user_id=conversation.user_id,
                escalation_reason=reason,
                escalation_type=escalation_type,
                priority=priority,
                status=TicketStatus.OPEN,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(ticket)
            self.db.flush()  # populate ticket.id before auto-assign

            self._auto_assign(ticket)

            conversation.status = ConversationStatus.ESCALATED
            conversation.updated_at = datetime.now(timezone.utc)

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
        """
        Resolve a ticket: close it, decrement agent load, mark conversation resolved.
        """
        ticket = self.db.get(SupportTicket, ticket_id)
        if ticket is None:
            return None

        try:
            ticket.status = TicketStatus.RESOLVED
            ticket.resolved_at = datetime.now(timezone.utc)
            ticket.updated_at = datetime.now(timezone.utc)
            if notes:
                ticket.notes = notes

            self._decrement_agent(ticket.assigned_agent_id)

            conversation = self.db.get(Conversation, ticket.conversation_id)
            if conversation:
                conversation.status = ConversationStatus.RESOLVED
                conversation.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(ticket)
            return ticket
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auto_assign(self, ticket: SupportTicket) -> None:
        """
        Assign `ticket` to the least-loaded available agent.
        Uses SELECT FOR UPDATE SKIP LOCKED to prevent race conditions
        when multiple tickets are being assigned concurrently.
        No-op if no available agent exists.
        """
        agent = self.db.scalar(
            select(User)
            .where(User.role == UserRole.AGENT)
            .where(User.agent_status == AgentStatus.AVAILABLE)
            .order_by(User.current_ticket_count.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if agent is None:
            return

        ticket.assigned_agent_id = agent.id
        ticket.status = TicketStatus.ASSIGNED
        agent.current_ticket_count += 1

    def _decrement_agent(self, agent_id: int | None) -> None:
        if agent_id is None:
            return
        agent = self.db.get(User, agent_id)
        if agent and agent.current_ticket_count > 0:
            agent.current_ticket_count -= 1
