import hashlib
import logging
import re
from datetime import datetime, timezone

from app.config import settings
from app.core.database import db, new_id
from app.models.schemas import ChatType, InternalMessage, MessageType

logger = logging.getLogger(__name__)

_OTP_PATTERN = re.compile(
    r"(?i)(?:otp|one\s*time\s*password|verification|code\s+is)[:\s]*(\d{4,8})"
)
_OTP_STANDALONE = re.compile(
    r"(?i)(\d{4,8})\s*(?:is\s+(?:your|the)\s+(?:otp|verification\s+code|one\s*time\s*password))"
)
_CARD_FULL = re.compile(r"\b(\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4})\b")
_CARD_ENDING = re.compile(r"(?i)(?:ending|last\s+4)\s*(?:in\s+)?(\d{4})")
_BANK_REF = re.compile(r"(?i)(?:reference\s*#?\s*|ref\.?\s*:?\s*|txn\s+of\s+)([A-Za-z0-9]+)")

_DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")

_MSG_TYPE_MAP = {
    "text": MessageType.TEXT,
    "image": MessageType.IMAGE,
    "document": MessageType.DOCUMENT,
    "audio": MessageType.AUDIO,
    "video": MessageType.VIDEO,
    "location": MessageType.LOCATION,
    "contacts": MessageType.CONTACT,
    "sticker": MessageType.STICKER,
}


def redact_pii(text: str) -> str:
    if not text:
        return text
    result = _OTP_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED:OTP]"), text)
    result = _OTP_STANDALONE.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED:OTP]"), result)
    result = _CARD_FULL.sub("[REDACTED:CARD]", result)
    result = _CARD_ENDING.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED:CARD]"), result)
    result = _BANK_REF.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED:BANK_REF]"), result)
    return result


def _detect_language(text: str) -> str:
    if not text:
        return "en"
    if _DEVANAGARI_RANGE.search(text):
        return "hi"
    return "en"


def _extract_content(msg: dict, msg_type: str) -> str:
    if msg_type == "text":
        return (msg.get("text") or {}).get("body", "")
    if msg_type == "image":
        return (msg.get("image") or {}).get("caption", "")
    if msg_type == "video":
        return (msg.get("video") or {}).get("caption", "")
    if msg_type == "document":
        return (msg.get("document") or {}).get("caption", "")
    return ""


def _extract_media_info(msg: dict, msg_type: str) -> tuple[str | None, str | None, str | None]:
    media_block = msg.get(msg_type) if msg_type in ("image", "document", "audio", "video", "sticker") else None
    if not media_block or not isinstance(media_block, dict):
        return None, None, None
    return (
        media_block.get("id"),
        media_block.get("filename"),
        media_block.get("mime_type"),
    )


def _parse_timestamp(raw) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        except (ValueError, OSError):
            pass
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _detect_bot_mention(content: str) -> tuple[bool, str | None]:
    tag = settings.bot_mention_tag
    if not content or tag not in content.lower():
        return False, None
    idx = content.lower().index(tag.lower())
    command = content[idx + len(tag):].strip()
    return True, command or None


async def _resolve_sender_name(sender_id: str, profile_name: str = "") -> str:
    try:
        row = await db.fetch_one(
            "SELECT name FROM employees WHERE whatsapp_id = ? OR id = ?",
            (sender_id, sender_id),
        )
        if row:
            return row["name"]
    except Exception:
        pass
    return profile_name or sender_id


async def parse_webhook_payload(payload: dict) -> InternalMessage | None:
    if not payload:
        return None

    if payload.get("object") == "whatsapp_business_account":
        return await _parse_whatsapp_cloud(payload)

    if payload.get("type") in ("message",) and payload.get("context"):
        return await _parse_openclaw(payload)

    logger.warning("Unrecognized webhook payload format")
    return None


async def _parse_whatsapp_cloud(payload: dict) -> InternalMessage | None:
    try:
        entry = payload.get("entry", [])
        if not entry:
            return None
        changes = entry[0].get("changes", [])
        if not changes:
            return None
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None

        msg = messages[0]
        contacts = value.get("contacts", [])
        profile_name = ""
        if contacts:
            profile_name = (contacts[0].get("profile") or {}).get("name", "")

        msg_id = msg.get("id", new_id())
        sender_id = msg.get("from", "")
        raw_type = msg.get("type", "text")
        msg_type = _MSG_TYPE_MAP.get(raw_type, MessageType.UNKNOWN)
        timestamp = _parse_timestamp(msg.get("timestamp"))
        content = _extract_content(msg, raw_type)
        media_id, media_filename, media_mime = _extract_media_info(msg, raw_type)

        is_forwarded = False
        ctx = msg.get("context") or {}
        if ctx.get("forwarded") or ctx.get("frequently_forwarded"):
            is_forwarded = True

        chat_id = msg.get("chat_id") or sender_id
        chat_type = ChatType.GROUP if value.get("metadata", {}).get("is_group") else ChatType.DM

        sender_name = await _resolve_sender_name(sender_id, profile_name)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
        language = _detect_language(content)
        is_mention, bot_command = _detect_bot_mention(content)
        redacted_content = redact_pii(content)

        return InternalMessage(
            id=msg_id,
            chat_id=chat_id,
            chat_type=chat_type,
            sender_id=sender_id,
            sender_name=sender_name,
            timestamp=timestamp,
            type=msg_type,
            content=redacted_content,
            content_hash=content_hash,
            media_id=media_id,
            media_filename=media_filename,
            media_mime=media_mime,
            is_forwarded=is_forwarded,
            is_bot_mention=is_mention,
            bot_command=bot_command,
            language=language,
            metadata={"raw_type": raw_type},
        )
    except Exception:
        logger.exception("Failed to parse WhatsApp Cloud payload")
        return None


async def _parse_openclaw(payload: dict) -> InternalMessage | None:
    try:
        ctx = payload.get("context", {})
        sender_id = ctx.get("from", "")
        content = ctx.get("content", "")
        timestamp = _parse_timestamp(ctx.get("timestamp"))
        chat_id = ctx.get("conversationId") or sender_id
        msg_id = ctx.get("messageId") or new_id()
        channel = ctx.get("channelId", "")

        metadata_raw = (ctx.get("metadata") or {}).get("raw", {})

        raw_type = metadata_raw.get("type", "text") if metadata_raw else "text"
        msg_type = _MSG_TYPE_MAP.get(raw_type, MessageType.TEXT)
        media_id, media_filename, media_mime = _extract_media_info(metadata_raw, raw_type) if metadata_raw else (None, None, None)

        is_forwarded = bool(metadata_raw.get("context", {}).get("forwarded")) if metadata_raw else False

        chat_type = ChatType.GROUP if "group" in channel.lower() else ChatType.DM

        profile_name = metadata_raw.get("profile_name", "") if metadata_raw else ""
        sender_name = await _resolve_sender_name(sender_id, profile_name)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
        language = _detect_language(content)
        is_mention, bot_command = _detect_bot_mention(content)
        redacted_content = redact_pii(content)

        return InternalMessage(
            id=msg_id,
            chat_id=chat_id,
            chat_type=chat_type,
            sender_id=sender_id,
            sender_name=sender_name,
            timestamp=timestamp,
            type=msg_type,
            content=redacted_content,
            content_hash=content_hash,
            media_id=media_id,
            media_filename=media_filename,
            media_mime=media_mime,
            is_forwarded=is_forwarded,
            is_bot_mention=is_mention,
            bot_command=bot_command,
            language=language,
            metadata={"channel": channel, "raw": metadata_raw},
        )
    except Exception:
        logger.exception("Failed to parse OpenClaw payload")
        return None


async def store_message(msg: InternalMessage) -> None:
    await db.execute(
        "INSERT INTO messages (id, chat_id, chat_type, sender_id, sender_name, "
        "timestamp, type, content, content_hash, media_id, media_filename, media_mime, "
        "is_forwarded, is_bot_mention, bot_command, language, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            msg.id,
            msg.chat_id,
            msg.chat_type.value,
            msg.sender_id,
            msg.sender_name,
            msg.timestamp.isoformat(),
            msg.type.value,
            msg.content,
            msg.content_hash,
            msg.media_id,
            msg.media_filename,
            msg.media_mime,
            msg.is_forwarded,
            msg.is_bot_mention,
            msg.bot_command,
            msg.language,
            str(msg.metadata),
        ),
    )


async def check_idempotency(message_id: str) -> bool:
    row = await db.fetch_one(
        "SELECT 1 FROM processed_messages WHERE message_id = ?",
        (message_id,),
    )
    return row is not None


async def mark_processed(message_id: str) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) "
        "VALUES (?, datetime('now'))",
        (message_id,),
    )


async def cleanup_idempotency() -> None:
    await db.execute(
        "DELETE FROM processed_messages WHERE processed_at < datetime('now', ?)",
        (f"-{settings.idempotency_ttl_seconds} seconds",),
    )
