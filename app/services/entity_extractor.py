import json
import logging
import re

from app.core.database import db, new_id
from app.models.schemas import InternalMessage

logger = logging.getLogger(__name__)

PRICE_PATTERNS = [
    re.compile(r'[₹$]\s*([\d,]+(?:\.\d+)?)\s*(?:/[-–]?\s*(?:per\s+)?(\w+))?', re.IGNORECASE),
    re.compile(r'(?:rate|price|cost|quoted?)\s*(?:[@:]|is|of)?\s*[₹$]?\s*([\d,]+(?:\.\d+)?)\s*(?:per\s+(\w+))?', re.IGNORECASE),
    re.compile(r'([\d,]+)\s*(?:lack|lakh|k)\b', re.IGNORECASE),
]
PHONE_PATTERN = re.compile(r'\+?\d{1,3}[\s-]?\d{4,5}[\s-]?\d{4,6}')


async def extract_and_store(message: InternalMessage) -> None:
    if not message.content:
        return

    text = message.content

    prices = _extract_prices(text)
    phones = _extract_phones(text)
    vendor_ids = await _match_vendors(text)
    has_media = message.media_id is not None

    if not prices and not phones and not vendor_ids and not has_media:
        return

    message_entity_id = await _ensure_message_entity(message)

    for amount, currency, unit in prices:
        price_entity_id = new_id()
        meta = json.dumps({"amount": amount, "currency": currency, "unit": unit})
        await db.execute(
            "INSERT OR IGNORE INTO entities (id, type, name, metadata, updated_at) "
            "VALUES (?, 'price', ?, ?, datetime('now'))",
            (price_entity_id, f"{currency}{amount}", meta),
        )
        await _link(message_entity_id, price_entity_id, "mentions_price", message.id)

    for phone in phones:
        phone_entity_id = await _ensure_entity("phone", phone, json.dumps({"number": phone}))
        await _link(message_entity_id, phone_entity_id, "mentions_phone", message.id)

    for vendor_id in vendor_ids:
        await _link(message_entity_id, vendor_id, "mentions_vendor", message.id)

    if has_media:
        doc_entity_id = new_id()
        meta = json.dumps({
            "media_id": message.media_id,
            "filename": message.media_filename,
            "mime": message.media_mime,
        })
        await db.execute(
            "INSERT OR IGNORE INTO entities (id, type, name, metadata, updated_at) "
            "VALUES (?, 'document_ref', ?, ?, datetime('now'))",
            (doc_entity_id, message.media_filename or message.media_id, meta),
        )
        await _link(message_entity_id, doc_entity_id, "attached_document", message.id)

    logger.debug(
        "Extracted from message %s: prices=%d phones=%d vendors=%d media=%s",
        message.id, len(prices), len(phones), len(vendor_ids), has_media,
    )


def _extract_prices(text: str) -> list[tuple[str, str, str]]:
    results = []
    for pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            amount = match.group(1).replace(",", "")
            unit = ""
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                unit = match.group(2)

            currency = "INR"
            prefix = text[max(0, match.start() - 1):match.start() + 1]
            if "$" in prefix:
                currency = "USD"

            if pattern == PRICE_PATTERNS[2]:
                raw = amount
                suffix = match.group(0).lower()
                if "lack" in suffix or "lakh" in suffix:
                    amount = str(float(raw) * 100000)
                elif "k" in suffix:
                    amount = str(float(raw) * 1000)

            results.append((amount, currency, unit))
    return results


def _extract_phones(text: str) -> list[str]:
    candidates = PHONE_PATTERN.findall(text)
    phones = []
    for p in candidates:
        digits = re.sub(r'[\s-]', '', p)
        if len(digits) >= 10:
            phones.append(p.strip())
    return phones


async def _match_vendors(text: str) -> list[str]:
    vendors = await db.fetch_all(
        "SELECT id, name FROM entities WHERE type = 'vendor'",
    )
    lower_text = text.lower()
    matched = []
    for v in vendors:
        if v["name"] and v["name"].lower() in lower_text:
            matched.append(v["id"])
    return matched


async def _ensure_message_entity(message: InternalMessage) -> str:
    entity_id = f"msg:{message.id}"
    existing = await db.fetch_one("SELECT id FROM entities WHERE id = ?", (entity_id,))
    if existing:
        return entity_id

    meta = json.dumps({
        "chat_id": message.chat_id,
        "sender": message.sender_name,
        "timestamp": message.timestamp.isoformat(),
    })
    await db.execute(
        "INSERT OR IGNORE INTO entities (id, type, name, metadata) "
        "VALUES (?, 'message', ?, ?)",
        (entity_id, f"Message from {message.sender_name}", meta),
    )
    return entity_id


async def _ensure_entity(entity_type: str, name: str, metadata: str) -> str:
    existing = await db.fetch_one(
        "SELECT id FROM entities WHERE type = ? AND name = ?",
        (entity_type, name),
    )
    if existing:
        await db.execute(
            "UPDATE entities SET updated_at = datetime('now') WHERE id = ?",
            (existing["id"],),
        )
        return existing["id"]

    entity_id = new_id()
    await db.execute(
        "INSERT INTO entities (id, type, name, metadata) VALUES (?, ?, ?, ?)",
        (entity_id, entity_type, name, metadata),
    )
    return entity_id


async def _link(source_id: str, target_id: str, relation_type: str, message_id: str) -> None:
    rel_id = new_id()
    await db.execute(
        "INSERT OR IGNORE INTO relationships (id, source_id, target_id, relation_type, source_message_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (rel_id, source_id, target_id, relation_type, message_id),
    )
