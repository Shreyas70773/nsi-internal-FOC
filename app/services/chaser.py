import logging
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.services.whatsapp_outbound import whatsapp
from app.services.email_service import email_service
from app.services import task_engine
from app.models.schemas import TaskStatus

logger = logging.getLogger(__name__)

IST_OFFSET = timedelta(hours=5, minutes=30)

ESCALATION_MATRIX = {
    "P0": {"nudge_hours": 2, "firm_hours": 4, "email_hours": 6},
    "P1": {"nudge_hours": 12, "firm_hours": 18, "email_hours": 24},
    "P2": {"nudge_hours": 24, "firm_hours": 48, "email_hours": 72},
}

TEMPLATES = {
    "gentle": "Hi {name}, friendly reminder: '{task}' — assigned {hours}h ago. Reply 'done' when complete.",
    "firm": "Hey {name}, '{task}' is now overdue ({hours}h). Any blockers? Reply 'done' or let me know.",
    "email_subject": "[OVERDUE] Task: {task}",
    "email_body": (
        "Task '{task}' assigned to {name} is overdue by {hours}h.\n"
        "Assigned by: {assigner}\nPlease complete or respond with an update."
    ),
}


def _ist_hour_now() -> int:
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + IST_OFFSET
    return ist_now.hour


def _hours_elapsed(created_at_str: str) -> float:
    created = datetime.fromisoformat(created_at_str).replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    return delta.total_seconds() / 3600


async def chaser_tick() -> None:
    hour = _ist_hour_now()
    if settings.quiet_window_start_hour <= hour < settings.quiet_window_end_hour:
        logger.debug("Chaser skipped — quiet window (%02d:xx IST)", hour)
        return

    tasks = await task_engine.get_overdue_tasks()
    if not tasks:
        logger.debug("Chaser tick — no overdue tasks")
        return

    logger.info("Chaser tick — processing %d overdue task(s)", len(tasks))

    for task in tasks:
        try:
            await _process_task(task)
        except Exception:
            logger.exception("Chaser error on task %s", task.get("id", "?"))


async def _process_task(task: dict) -> None:
    priority = task["priority"]
    matrix = ESCALATION_MATRIX.get(priority)
    if not matrix:
        logger.warning("Unknown priority %s for task %s", priority, task["id"])
        return

    hours = _hours_elapsed(task["created_at"])
    status = task["status"]
    name = task.get("assignee_name", "there")
    chat_id = task.get("assignee_whatsapp_id") or task["source_chat_id"]
    now_iso = datetime.now(timezone.utc).isoformat()
    hours_rounded = round(hours)

    assigner = await task_engine.resolve_employee(task.get("assigner_id", ""))
    assigner_name = (assigner or {}).get("name", "unknown")

    template_vars = {
        "name": name,
        "task": task["description"],
        "hours": hours_rounded,
        "assigner": assigner_name,
    }

    if hours >= matrix["email_hours"] and status != TaskStatus.ESCALATED.value:
        sent = await email_service.send_escalation(task, name, assigner_name)
        logger.info(
            "ESCALATE task %s — email %s",
            task["id"],
            "sent" if sent else "skipped (no config)",
        )
        await task_engine.update_task_status(
            task["id"],
            TaskStatus.ESCALATED.value,
            last_nudged_at=now_iso,
            nudge_count=(task.get("nudge_count") or 0) + 1,
        )
        return

    if hours >= matrix["firm_hours"] and status == TaskStatus.NUDGED_1.value:
        msg = TEMPLATES["firm"].format(**template_vars)
        await whatsapp.send_text(chat_id, msg)
        await task_engine.update_task_status(
            task["id"],
            TaskStatus.NUDGED_2.value,
            last_nudged_at=now_iso,
            nudge_count=(task.get("nudge_count") or 0) + 1,
        )
        return

    if hours >= matrix["nudge_hours"] and status == TaskStatus.PENDING.value:
        msg = TEMPLATES["gentle"].format(**template_vars)
        await whatsapp.send_text(chat_id, msg)
        await task_engine.update_task_status(
            task["id"],
            TaskStatus.NUDGED_1.value,
            last_nudged_at=now_iso,
            nudge_count=(task.get("nudge_count") or 0) + 1,
        )
