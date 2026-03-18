import logging
from datetime import datetime, timezone

import httpx
import msal

from app.config import settings
from app.core.database import db

logger = logging.getLogger(__name__)


class EmailService:

    def __init__(self) -> None:
        self._msal_app: msal.ConfidentialClientApplication | None = None
        self._scopes = ["https://graph.microsoft.com/.default"]

    def _get_msal_app(self) -> msal.ConfidentialClientApplication | None:
        if self._msal_app is not None:
            return self._msal_app

        if not all([settings.azure_client_id, settings.azure_client_secret, settings.azure_tenant_id]):
            logger.warning("Azure credentials not configured — email disabled")
            return None

        self._msal_app = msal.ConfidentialClientApplication(
            settings.azure_client_id,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
            client_credential=settings.azure_client_secret,
        )
        return self._msal_app

    async def _acquire_token(self) -> str | None:
        app = self._get_msal_app()
        if app is None:
            return None

        result = app.acquire_token_for_client(scopes=self._scopes)
        if "access_token" in result:
            return result["access_token"]

        logger.error(
            "Failed to acquire token: %s",
            result.get("error_description", result.get("error")),
        )
        return None

    async def send_email(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> bool:
        token = await self._acquire_token()
        if not token:
            logger.warning("No token available — skipping email send")
            return False

        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                "ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])],
            }
        }

        url = f"https://graph.microsoft.com/v1.0/users/{settings.email_from}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 202:
                logger.info("Email sent to %s — subject: %s", to, subject)
                return True
            logger.error("Graph API error %d: %s", resp.status_code, resp.text)
            return False
        except Exception:
            logger.exception("Failed to send email")
            return False

    async def send_escalation(
        self,
        task: dict,
        assignee_name: str,
        assigner_name: str,
    ) -> bool:
        try:
            employee = await db.fetch_one(
                "SELECT email FROM employees WHERE id = ?",
                (task["assignee_id"],),
            )
            to_addr = (employee or {}).get("email") or settings.email_from

            created = datetime.fromisoformat(task["created_at"]).replace(tzinfo=timezone.utc)
            hours_overdue = round((datetime.now(timezone.utc) - created).total_seconds() / 3600)

            subject = f"[OVERDUE] Task: {task['description']}"
            body = (
                f"Task: {task['description']}\n"
                f"Assignee: {assignee_name}\n"
                f"Hours overdue: {hours_overdue}\n"
                f"Assigned by: {assigner_name}\n"
                f"Chat context: {task.get('source_chat_id', 'N/A')}\n"
            )

            cc = [addr for addr in [settings.email_always_cc] if addr]
            if task.get("priority") == "P0" and settings.email_p0_cc:
                cc.append(settings.email_p0_cc)

            return await self.send_email([to_addr], subject, body, cc=cc or None)
        except Exception:
            logger.exception("Failed to build escalation email for task %s", task.get("id"))
            return False


email_service = EmailService()
