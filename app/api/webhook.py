import logging
import uuid

from fastapi import APIRouter, Request

from app.config import settings
from app.core.queue import message_queue
from app.models.schemas import WebhookAck
from app.services.ingress import check_idempotency, mark_processed

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_message_id(payload: dict) -> str:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        pass

    oc_id = payload.get("context", {}).get("messageId")
    if oc_id:
        return oc_id

    return uuid.uuid4().hex


@router.post(settings.webhook_path)
async def receive_webhook(request: Request):
    payload = await request.json()
    message_id = _extract_message_id(payload)

    if await check_idempotency(message_id):
        return WebhookAck(status="ok", message_id=message_id)

    await mark_processed(message_id)
    await message_queue.enqueue(payload)

    logger.info("Webhook accepted message_id=%s", message_id)
    return WebhookAck(status="ok", message_id=message_id)
