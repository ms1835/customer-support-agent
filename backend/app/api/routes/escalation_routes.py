from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_escalation_service, get_ticket_service, require_customer
from app.models.support_tickets import EscalationType
from app.models.users import User
from app.schemas.ticket_schema import EscalationRequest, TicketResponse
from app.services.escalation_service import EscalationService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/conversations", tags=["Escalation"])


@router.post("/{conversation_id}/escalate", response_model=TicketResponse, status_code=201)
def escalate_conversation(
    conversation_id: int,
    body: EscalationRequest = EscalationRequest(),
    svc: EscalationService = Depends(get_escalation_service),
    _: User = Depends(require_customer),
):
    """
    Manually escalate a conversation to a human agent.
    Creates a SupportTicket, marks the conversation ESCALATED,
    and auto-assigns to the least-loaded available agent.
    Idempotent: returns the existing ticket if already escalated.
    """
    reason = body.reason or "User requested to speak with a human support agent."
    try:
        ticket = svc.escalate_conversation(
            conversation_id=conversation_id,
            reason=reason,
            escalation_type=EscalationType.USER_REQUESTED,
            priority=body.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ticket


@router.get("/{conversation_id}/ticket", response_model=TicketResponse)
def get_conversation_ticket(
    conversation_id: int,
    svc: TicketService = Depends(get_ticket_service),
    _: User = Depends(get_current_user),
):
    """Fetch the support ticket associated with an escalated conversation."""
    ticket = svc.get_ticket_by_conversation(conversation_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="No ticket found for this conversation")
    return ticket
