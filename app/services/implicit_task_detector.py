import json
import logging
import re

from app.core.database import db
from app.models.schemas import InternalMessage
from app.services.llm_gateway import llm_gateway
from app.services.task_engine import create_task, resolve_employee
from app.services.whatsapp_outbound import whatsapp

logger = logging.getLogger(__name__)

_ACTION_PATTERNS = re.compile(
    r'\b(?:please|pls|kindly|need\s+to|have\s+to|must|should|make\s+sure|'
    r'follow\s+up|check\s+with|pay|send|call|email|remind|arrange|organize|'
    r'book|schedule|prepare|submit|deliver|dispatch|transfer|confirm)\b',
    re.IGNORECASE,
)

_IMPLICIT_TASK_PROMPT = """Analyze this WhatsApp message. Does it contain an implicit task assignment?

Message: "{message}"
Sender: {sender}
Known employees: {employees}

If this IS an implicit task, respond with JSON:
{{"is_task": true, "assignee": "name", "description": "concise task", "priority": "P0|P1|P2", "deadline": null}}

If this is NOT a task (just conversation, information sharing, or general discussion), respond with:
{{"is_task": false}}

Be conservative — only flag clear action items directed at a specific person. General discussion is NOT a task.
Respond with ONLY valid JSON, nothing else."""

_MIN_CONTENT_LENGTH = 10


async def _get_employee_names() -> list[dict]:
    return await db.fetch_all("SELECT id, name, whatsapp_id FROM employees")


def _any_employee_mentioned(text: str, employees: list[dict]) -> bool:
    text_lower = text.lower()
    for emp in employees:
        name = emp.get("name", "")
        if not name:
            continue
        if name.lower() in text_lower:
            return True
        parts = name.lower().split()
        if any(len(p) > 2 and p in text_lower for p in parts):
            return True
    return False


async def detect_implicit_tasks(message: InternalMessage) -> None:
    if message.is_bot_mention:
        logger.debug("Skipping bot-mention message %s", message.id)
        return

    content = (message.content or "").strip()
    if len(content) < _MIN_CONTENT_LENGTH:
        logger.debug("Skipping short message %s (%d chars)", message.id, len(content))
        return

    if not _ACTION_PATTERNS.search(content):
        logger.debug("No action keywords in message %s", message.id)
        return

    employees = await _get_employee_names()
    if not employees:
        logger.debug("No employees in database — skipping implicit detection")
        return

    if not _any_employee_mentioned(content, employees):
        logger.debug("No employee names found in message %s", message.id)
        return

    logger.info("Message %s passed keyword+name gate — confirming with LLM", message.id)

    employee_names = ", ".join(e["name"] for e in employees if e.get("name"))
    prompt = _IMPLICIT_TASK_PROMPT.format(
        message=content,
        sender=message.sender_name or message.sender_id,
        employees=employee_names,
    )

    try:
        result = await llm_gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            request_type="implicit_task_detection",
        )
    except Exception:
        logger.exception("LLM call failed for implicit task detection on message %s", message.id)
        return

    raw = (result.get("content") or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON for message %s: %s", message.id, raw[:200])
        return

    if not parsed.get("is_task"):
        logger.info("LLM determined message %s is not a task", message.id)
        return

    assignee_name = parsed.get("assignee", "")
    description = parsed.get("description", content[:100])
    priority = parsed.get("priority", "P1")
    deadline = parsed.get("deadline")

    if priority not in ("P0", "P1", "P2"):
        priority = "P1"

    employee = await resolve_employee(assignee_name) if assignee_name else None
    if not employee:
        logger.warning(
            "LLM identified task in message %s but assignee '%s' not found",
            message.id, assignee_name,
        )
        return

    task = await create_task(
        assigner_id=message.sender_id,
        assignee_id=employee["id"],
        description=description,
        priority=priority,
        source_chat_id=message.chat_id,
        source_message_id=message.id,
        deadline=deadline,
    )

    await whatsapp.send_text(
        message.chat_id,
        f"I detected a task: '{description}' assigned to {employee['name']}. "
        f"Reply 'cancel' if this was incorrect.",
    )
    logger.info(
        "Implicit task %s created from message %s: '%s' -> %s [%s]",
        task["id"], message.id, description, employee["name"], priority,
    )
