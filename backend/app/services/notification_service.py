import json
import logging
import threading

import boto3

from app.config import settings
from app.models.support_tickets import SupportTicket

logger = logging.getLogger(__name__)


def _enum_value(value) -> str:
    return getattr(value, "value", str(value))


class NotificationService:
    """
    Sends escalation notifications to the support team via AWS SES.
    The email layout lives in an SES template (settings.SES_TEMPLATE_NAME);
    this service only supplies the data.
    """

    @staticmethod
    def _enabled() -> bool:
        return bool(settings.SES_SENDER_EMAIL and settings.SUPPORT_TEAM_EMAILS and settings.AWS_REGION)

    @classmethod
    def notify_ticket_created(cls, ticket: SupportTicket) -> None:
        """
        Fire-and-forget email about a newly raised ticket. Never raises:
        a notification failure must not break the escalation.
        """
        if not cls._enabled():
            logger.info("SES notifications disabled (sender/recipients/region not configured).")
            return

        try:
            # Copy ORM data into plain values here — the send runs in another thread
            # and must not touch the request's DB session.
            customer = ticket.user
            agent = ticket.assigned_agent
            template_data = {
                "ticket_id": ticket.id,
                "conversation_id": ticket.conversation_id,
                "customer_name": customer.name if customer else "Unknown",
                "customer_email": customer.email if customer else "Unknown",
                "reason": ticket.escalation_reason or "-",
                "escalation_type": _enum_value(ticket.escalation_type),
                "priority": _enum_value(ticket.priority),
                "status": _enum_value(ticket.status),
                "assigned_agent": agent.name if agent else "Unassigned",
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M UTC") if ticket.created_at else "-",
                "dashboard_url": settings.FRONTEND_URL,
            }
        except Exception:
            logger.exception("Failed to build ticket notification for ticket %s", getattr(ticket, "id", None))
            return

        threading.Thread(target=cls._send, args=(template_data,), daemon=True).start()

    @classmethod
    def _send(cls, template_data: dict) -> None:
        try:
            client_kwargs = {"region_name": settings.AWS_REGION}
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
                client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            ses = boto3.client("sesv2", **client_kwargs)

            ses.send_email(
                FromEmailAddress=settings.SES_SENDER_EMAIL,
                Destination={"ToAddresses": settings.SUPPORT_TEAM_EMAILS},
                Content={
                    "Template": {
                        "TemplateName": settings.SES_TEMPLATE_NAME,
                        "TemplateData": json.dumps(template_data),
                    }
                },
            )
            logger.info("Escalation email sent for ticket #%s", template_data["ticket_id"])
        except Exception:
            logger.exception("Failed to send escalation email for ticket #%s", template_data.get("ticket_id"))
