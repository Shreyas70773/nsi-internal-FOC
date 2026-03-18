import logging
from datetime import datetime, timezone

from app.config import settings
from app.core.database import db, new_id
from app.models.schemas import TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

COMPLETION_KEYWORDS = {"done", "completed", "paid", "ok", "finished", "sent"}

ACTIVE_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.NUDGED_1.value,
    TaskStatus.NUDGED_2.value,
    TaskStatus.ESCALATED.value,
)


async def resolve_employee(identifier: str) -> dict | None:
    row = await db.fetch_one("SELECT * FROM employees WHERE id = ?", (identifier,))
    if row:
        return row
    row = await db.fetch_one("SELECT * FROM employees WHERE whatsapp_id = ?", (identifier,))
    if row:
        return row
    row = await db.fetch_one(
        "SELECT * FROM employees WHERE LOWER(name) LIKE ?",
        (f"%{identifier.lower()}%",),
    )
    return row


async def create_task(
    assigner_id: str,
    assignee_id: str,
    description: str,
    priority: str,
    source_chat_id: str,
    source_message_id: str,
    deadline: str | None = None,
) -> dict:
    task_id = new_id()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO tasks
            (id, assigner_id, assignee_id, description, priority, status,
             source_chat_id, source_message_id, deadline, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id, assigner_id, assignee_id, description, priority,
            TaskStatus.PENDING.value, source_chat_id, source_message_id,
            deadline, now, now,
        ),
    )
    task = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    logger.info("Task %s created: '%s' [%s]", task_id, description, priority)
    return task


async def update_task_status(task_id: str, new_status: str, **kwargs) -> dict | None:
    task = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        logger.warning("Task %s not found for status update", task_id)
        return None

    now = datetime.now(timezone.utc).isoformat()
    set_clauses = ["status = ?", "updated_at = ?"]
    params: list = [new_status, now]

    for col in ("completed_at", "last_nudged_at", "nudge_count"):
        if col in kwargs:
            set_clauses.append(f"{col} = ?")
            params.append(kwargs[col])

    params.append(task_id)

    await db.execute(
        f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(params),
    )
    updated = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    logger.info("Task %s status -> %s", task_id, new_status)
    return updated


async def get_pending_tasks(assignee_id: str | None = None) -> list[dict]:
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    if assignee_id:
        return await db.fetch_all(
            f"SELECT * FROM tasks WHERE status IN ({placeholders}) AND assignee_id = ? ORDER BY created_at",
            (*ACTIVE_STATUSES, assignee_id),
        )
    return await db.fetch_all(
        f"SELECT * FROM tasks WHERE status IN ({placeholders}) ORDER BY created_at",
        ACTIVE_STATUSES,
    )


async def get_overdue_tasks() -> list[dict]:
    return await db.fetch_all(
        """
        SELECT t.*, e.name AS assignee_name, e.whatsapp_id AS assignee_whatsapp_id
        FROM tasks t
        JOIN employees e ON t.assignee_id = e.id
        WHERE t.status IN ('pending', 'nudged_1', 'nudged_2')
          AND (t.last_nudged_at IS NULL
               OR t.last_nudged_at < datetime('now', '-55 minutes'))
        ORDER BY t.created_at
        """,
    )


async def detect_completion(chat_id: str, sender_id: str, text: str) -> bool:
    words = set(text.lower().split())
    if not words & COMPLETION_KEYWORDS:
        return False

    employee = await resolve_employee(sender_id)
    lookup_id = employee["id"] if employee else sender_id

    task = await db.fetch_one(
        """
        SELECT * FROM tasks
        WHERE assignee_id = ? AND source_chat_id = ?
          AND status IN ('pending', 'nudged_1', 'nudged_2')
        ORDER BY created_at DESC LIMIT 1
        """,
        (lookup_id, chat_id),
    )
    if not task:
        return False

    now = datetime.now(timezone.utc).isoformat()
    await update_task_status(
        task["id"],
        TaskStatus.COMPLETED.value,
        completed_at=now,
    )
    logger.info("Task %s auto-completed by sender %s", task["id"], sender_id)
    return True


async def cancel_task(task_id: str) -> bool:
    task = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return False
    await update_task_status(task_id, TaskStatus.CANCELLED.value)
    return True


async def pause_task(task_id: str) -> bool:
    task = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return False
    await update_task_status(task_id, TaskStatus.PAUSED.value)
    return True


async def get_task_summary(assignee_id: str | None = None) -> str:
    tasks = await get_pending_tasks(assignee_id)
    if not tasks:
        return "No pending tasks."

    lines: list[str] = []
    for i, t in enumerate(tasks, 1):
        status_icon = {"pending": "⏳", "nudged_1": "🔔", "nudged_2": "⚠️", "escalated": "🚨"}.get(
            t["status"], "❓"
        )
        deadline_part = f" | Due: {t['deadline']}" if t.get("deadline") else ""
        lines.append(
            f"{i}. {status_icon} [{t['priority']}] {t['description']}{deadline_part}"
        )

    header = f"*Pending Tasks ({len(tasks)}):*"
    return f"{header}\n" + "\n".join(lines)
