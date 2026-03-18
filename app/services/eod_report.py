import logging
from datetime import datetime, timezone

from app.core.database import db
from app.services.whatsapp_outbound import whatsapp

logger = logging.getLogger(__name__)


async def _get_report_chat_id() -> str | None:
    row = await db.fetch_one(
        "SELECT DISTINCT chat_id FROM messages "
        "WHERE chat_type='group' ORDER BY timestamp DESC LIMIT 1"
    )
    return row["chat_id"] if row else None


async def _fetch_daily_metrics() -> dict:
    tasks_created = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(created_at) = date('now')"
    )
    tasks_completed = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(completed_at) = date('now')"
    )
    tasks_overdue = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks "
        "WHERE status IN ('pending','nudged_1','nudged_2','escalated') "
        "AND deadline IS NOT NULL AND deadline < datetime('now')"
    )
    tasks_pending = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks "
        "WHERE status IN ('pending','nudged_1','nudged_2','escalated')"
    )
    files_uploaded = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM documents WHERE date(created_at) = date('now')"
    )
    docs_generated = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM generated_documents WHERE date(created_at) = date('now')"
    )
    token_row = await db.fetch_one(
        "SELECT COALESCE(SUM(total_tokens), 0) AS tokens, "
        "COALESCE(SUM(latency_ms), 0) AS latency "
        "FROM token_usage WHERE date(created_at) = date('now')"
    )

    return {
        "tasks_created": (tasks_created or {}).get("n", 0),
        "tasks_completed": (tasks_completed or {}).get("n", 0),
        "tasks_overdue": (tasks_overdue or {}).get("n", 0),
        "tasks_pending": (tasks_pending or {}).get("n", 0),
        "files_uploaded": (files_uploaded or {}).get("n", 0),
        "docs_generated": (docs_generated or {}).get("n", 0),
        "tokens_used": (token_row or {}).get("tokens", 0),
        "total_latency_ms": (token_row or {}).get("latency", 0),
    }


async def _fetch_weekly_metrics() -> dict:
    tasks_created = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks WHERE created_at >= datetime('now', '-7 days')"
    )
    tasks_completed = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at >= datetime('now', '-7 days')"
    )
    tasks_overdue = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks "
        "WHERE status IN ('pending','nudged_1','nudged_2','escalated') "
        "AND deadline IS NOT NULL AND deadline < datetime('now')"
    )
    tasks_pending = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM tasks "
        "WHERE status IN ('pending','nudged_1','nudged_2','escalated')"
    )
    files_uploaded = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM documents WHERE created_at >= datetime('now', '-7 days')"
    )
    docs_generated = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM generated_documents WHERE created_at >= datetime('now', '-7 days')"
    )
    token_row = await db.fetch_one(
        "SELECT COALESCE(SUM(total_tokens), 0) AS tokens, "
        "COALESCE(SUM(latency_ms), 0) AS latency "
        "FROM token_usage WHERE created_at >= datetime('now', '-7 days')"
    )

    return {
        "tasks_created": (tasks_created or {}).get("n", 0),
        "tasks_completed": (tasks_completed or {}).get("n", 0),
        "tasks_overdue": (tasks_overdue or {}).get("n", 0),
        "tasks_pending": (tasks_pending or {}).get("n", 0),
        "files_uploaded": (files_uploaded or {}).get("n", 0),
        "docs_generated": (docs_generated or {}).get("n", 0),
        "tokens_used": (token_row or {}).get("tokens", 0),
        "total_latency_ms": (token_row or {}).get("latency", 0),
    }


async def _fetch_top_pending(limit: int = 5) -> list[dict]:
    return await db.fetch_all(
        "SELECT t.description, t.priority, COALESCE(e.name, t.assignee_id) AS assignee_name "
        "FROM tasks t "
        "LEFT JOIN employees e ON t.assignee_id = e.id "
        "WHERE t.status IN ('pending','nudged_1','nudged_2','escalated') "
        "ORDER BY CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, "
        "t.created_at ASC LIMIT ?",
        (limit,),
    )


async def _fetch_employee_performance() -> list[dict]:
    return await db.fetch_all(
        "SELECT COALESCE(e.name, t.assignee_id) AS name, COUNT(*) AS completed "
        "FROM tasks t "
        "LEFT JOIN employees e ON t.assignee_id = e.id "
        "WHERE t.completed_at >= datetime('now', '-7 days') "
        "GROUP BY t.assignee_id "
        "ORDER BY completed DESC"
    )


def _format_report(date_label: str, metrics: dict, top_pending: list[dict]) -> str:
    lines = [
        f"📊 *EOD Report — {date_label}*",
        "",
        f"✅ Tasks Completed: {metrics['tasks_completed']}",
        f"📝 Tasks Created: {metrics['tasks_created']}",
        f"⏳ Tasks Pending: {metrics['tasks_pending']}",
        f"⚠️ Tasks Overdue: {metrics['tasks_overdue']}",
        f"📁 Files Uploaded: {metrics['files_uploaded']}",
        f"📄 Documents Generated: {metrics['docs_generated']}",
        f"🤖 LLM Tokens Used: {metrics['tokens_used']:,}",
    ]

    if top_pending:
        lines.append("")
        lines.append("*Top Pending:*")
        for i, t in enumerate(top_pending, 1):
            lines.append(f"{i}. [{t['priority']}] {t['description']} → {t['assignee_name']}")

    return "\n".join(lines)


def _format_weekly(
    date_label: str,
    metrics: dict,
    top_pending: list[dict],
    performance: list[dict],
) -> str:
    lines = [
        f"📊 *Weekly Summary — {date_label}*",
        "",
        f"✅ Tasks Completed: {metrics['tasks_completed']}",
        f"📝 Tasks Created: {metrics['tasks_created']}",
        f"⏳ Tasks Pending: {metrics['tasks_pending']}",
        f"⚠️ Tasks Overdue: {metrics['tasks_overdue']}",
        f"📁 Files Uploaded: {metrics['files_uploaded']}",
        f"📄 Documents Generated: {metrics['docs_generated']}",
        f"🤖 LLM Tokens Used: {metrics['tokens_used']:,}",
    ]

    if performance:
        lines.append("")
        lines.append("*Employee Performance (tasks completed):*")
        for emp in performance:
            lines.append(f"  • {emp['name']}: {emp['completed']}")

    if top_pending:
        lines.append("")
        lines.append("*Top Pending:*")
        for i, t in enumerate(top_pending, 1):
            lines.append(f"{i}. [{t['priority']}] {t['description']} → {t['assignee_name']}")

    return "\n".join(lines)


async def generate_eod_report() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metrics = await _fetch_daily_metrics()
    top_pending = await _fetch_top_pending(limit=5)
    report = _format_report(today, metrics, top_pending)

    chat_id = await _get_report_chat_id()
    if chat_id:
        await whatsapp.send_text(chat_id, report)
        logger.info("EOD report sent to %s", chat_id)
    else:
        logger.warning("No group chat found — EOD report not sent")

    return report


async def generate_weekly_summary() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_label = f"Week ending {today}"
    metrics = await _fetch_weekly_metrics()
    top_pending = await _fetch_top_pending(limit=10)
    performance = await _fetch_employee_performance()
    report = _format_weekly(date_label, metrics, top_pending, performance)

    chat_id = await _get_report_chat_id()
    if chat_id:
        await whatsapp.send_text(chat_id, report)
        logger.info("Weekly summary sent to %s", chat_id)
    else:
        logger.warning("No group chat found — weekly summary not sent")

    return report
