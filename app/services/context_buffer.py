import hashlib
import json
import logging
from datetime import datetime, timezone

from app.config import settings
from app.core.database import db, new_id
from app.services.whatsapp_outbound import whatsapp

logger = logging.getLogger(__name__)


def _parse_json_list(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def open_buffer(
    user_id: str,
    chat_id: str,
    intent: str,
    message_id: str | None = None,
    media_id: str | None = None,
) -> dict:
    intent_hash = hashlib.md5(f"{user_id}:{chat_id}:{intent}".encode()).hexdigest()

    existing = await db.fetch_one(
        "SELECT * FROM context_buffers WHERE user_id = ? AND chat_id = ? AND intent_hash = ? AND status = 'collecting'",
        (user_id, chat_id, intent_hash),
    )

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        message_ids = _parse_json_list(existing["message_ids"])
        media_ids = _parse_json_list(existing["media_ids"])
        if message_id and message_id not in message_ids:
            message_ids.append(message_id)
        if media_id and media_id not in media_ids:
            media_ids.append(media_id)

        await db.execute(
            "UPDATE context_buffers SET message_ids = ?, media_ids = ?, last_activity_at = ? WHERE id = ?",
            (json.dumps(message_ids), json.dumps(media_ids), now, existing["id"]),
        )
        logger.info("Buffer %s updated for user %s", existing["id"], user_id)
        return await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (existing["id"],))

    buffer_id = new_id()
    message_ids = [message_id] if message_id else []
    media_ids = [media_id] if media_id else []
    timeout = settings.context_buffer_timeout_minutes

    await db.execute(
        """
        INSERT INTO context_buffers
            (id, user_id, chat_id, intent, intent_hash, status,
             message_ids, media_ids, created_at, last_activity_at, timeout_minutes)
        VALUES (?, ?, ?, ?, ?, 'collecting', ?, ?, ?, ?, ?)
        """,
        (
            buffer_id, user_id, chat_id, intent, intent_hash,
            json.dumps(message_ids), json.dumps(media_ids),
            now, now, timeout,
        ),
    )

    await whatsapp.send_text(
        chat_id,
        f"Got it, I'm collecting. Send me everything and say 'Done' when ready, "
        f"or I'll process in {timeout} minutes.",
    )
    logger.info("Buffer %s created for user %s intent=%s", buffer_id, user_id, intent)
    return await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buffer_id,))


async def add_to_buffer(
    user_id: str,
    chat_id: str,
    message_id: str | None = None,
    media_id: str | None = None,
) -> dict | None:
    buf = await db.fetch_one(
        "SELECT * FROM context_buffers WHERE user_id = ? AND chat_id = ? AND status = 'collecting' ORDER BY last_activity_at DESC LIMIT 1",
        (user_id, chat_id),
    )
    if not buf:
        return None

    message_ids = _parse_json_list(buf["message_ids"])
    media_ids = _parse_json_list(buf["media_ids"])
    if message_id and message_id not in message_ids:
        message_ids.append(message_id)
    if media_id and media_id not in media_ids:
        media_ids.append(media_id)

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE context_buffers SET message_ids = ?, media_ids = ?, last_activity_at = ? WHERE id = ?",
        (json.dumps(message_ids), json.dumps(media_ids), now, buf["id"]),
    )
    logger.debug("Buffer %s: added msg=%s media=%s", buf["id"], message_id, media_id)
    return await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buf["id"],))


async def close_buffer(buffer_id: str, status: str = "complete") -> dict | None:
    buf = await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buffer_id,))
    if not buf:
        logger.warning("close_buffer: buffer %s not found", buffer_id)
        return None

    await db.execute(
        "UPDATE context_buffers SET status = ? WHERE id = ?",
        (status, buffer_id),
    )
    logger.info("Buffer %s closed with status=%s", buffer_id, status)
    return await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buffer_id,))


async def get_active_buffer(user_id: str, chat_id: str) -> dict | None:
    return await db.fetch_one(
        "SELECT * FROM context_buffers WHERE user_id = ? AND chat_id = ? AND status = 'collecting' ORDER BY last_activity_at DESC LIMIT 1",
        (user_id, chat_id),
    )


async def check_timeouts() -> list[dict]:
    timed_out = await db.fetch_all(
        """
        SELECT * FROM context_buffers
        WHERE status = 'collecting'
          AND datetime(last_activity_at, '+' || timeout_minutes || ' minutes') < datetime('now')
        """,
    )

    results = []
    for buf in timed_out:
        await db.execute(
            "UPDATE context_buffers SET status = 'timed_out' WHERE id = ?",
            (buf["id"],),
        )
        updated = await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buf["id"],))
        results.append(updated)
        logger.info("Buffer %s timed out (user=%s, chat=%s)", buf["id"], buf["user_id"], buf["chat_id"])

    return results


async def reopen_if_matching(user_id: str, chat_id: str, intent: str) -> dict | None:
    intent_hash = hashlib.md5(f"{user_id}:{chat_id}:{intent}".encode()).hexdigest()

    buf = await db.fetch_one(
        """
        SELECT * FROM context_buffers
        WHERE user_id = ? AND chat_id = ? AND intent_hash = ? AND status = 'timed_out'
          AND datetime(last_activity_at, '+' || (timeout_minutes + 5) || ' minutes') > datetime('now')
        ORDER BY last_activity_at DESC LIMIT 1
        """,
        (user_id, chat_id, intent_hash),
    )
    if not buf:
        return None

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE context_buffers SET status = 'collecting', last_activity_at = ? WHERE id = ?",
        (now, buf["id"]),
    )
    logger.info("Buffer %s reopened for user %s", buf["id"], user_id)
    return await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buf["id"],))


async def get_buffer_messages(buffer_id: str) -> list[dict]:
    buf = await db.fetch_one("SELECT * FROM context_buffers WHERE id = ?", (buffer_id,))
    if not buf:
        return []

    message_ids = _parse_json_list(buf["message_ids"])
    if not message_ids:
        return []

    placeholders = ",".join("?" for _ in message_ids)
    return await db.fetch_all(
        f"SELECT * FROM messages WHERE id IN ({placeholders}) ORDER BY timestamp",
        tuple(message_ids),
    )
