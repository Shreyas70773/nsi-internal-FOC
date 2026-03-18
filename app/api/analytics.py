import logging

from fastapi import APIRouter, Depends

from app.core.database import db
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/analytics/summary")
async def analytics_summary(_user: dict = Depends(get_current_user)):
    totals = await db.fetch_one(
        "SELECT "
        "  COUNT(*) AS tasks_total, "
        "  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS tasks_completed, "
        "  SUM(CASE WHEN deadline IS NOT NULL AND deadline < datetime('now') "
        "    AND status NOT IN ('completed', 'cancelled') THEN 1 ELSE 0 END) AS tasks_overdue, "
        "  SUM(CASE WHEN status IN ('pending','nudged_1','nudged_2','escalated') "
        "    THEN 1 ELSE 0 END) AS tasks_pending "
        "FROM tasks"
    )

    avg_row = await db.fetch_one(
        "SELECT AVG((julianday(completed_at) - julianday(created_at)) * 24) AS avg_hours "
        "FROM tasks WHERE status = 'completed' AND completed_at IS NOT NULL"
    )

    priority_rows = await db.fetch_all(
        "SELECT priority, "
        "  COUNT(*) AS total, "
        "  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed, "
        "  SUM(CASE WHEN deadline IS NOT NULL AND deadline < datetime('now') "
        "    AND status NOT IN ('completed','cancelled') THEN 1 ELSE 0 END) AS overdue "
        "FROM tasks GROUP BY priority"
    )
    by_priority = {}
    for r in priority_rows:
        by_priority[r["priority"]] = {
            "total": r["total"],
            "completed": r["completed"],
            "overdue": r["overdue"],
        }

    emp_rows = await db.fetch_all(
        "SELECT e.name, "
        "  COUNT(*) AS assigned, "
        "  SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) AS completed, "
        "  SUM(CASE WHEN t.deadline IS NOT NULL AND t.deadline < datetime('now') "
        "    AND t.status NOT IN ('completed','cancelled') THEN 1 ELSE 0 END) AS overdue, "
        "  AVG(CASE WHEN t.status = 'completed' AND t.completed_at IS NOT NULL "
        "    THEN (julianday(t.completed_at) - julianday(t.created_at)) * 24 "
        "    ELSE NULL END) AS avg_hours "
        "FROM tasks t "
        "JOIN employees e ON t.assignee_id = e.id "
        "GROUP BY e.id, e.name"
    )

    token_rows = await db.fetch_all(
        "SELECT provider, "
        "  SUM(total_tokens) AS tokens, "
        "  COUNT(*) AS requests, "
        "  SUM(COALESCE(cost_estimate_usd, 0)) AS cost "
        "FROM token_usage "
        "WHERE date(created_at) = date('now') "
        "GROUP BY provider"
    )
    token_total = sum(r["tokens"] or 0 for r in token_rows)
    token_cost = sum(r["cost"] or 0 for r in token_rows)

    return {
        "tasks_total": totals["tasks_total"] or 0,
        "tasks_completed": totals["tasks_completed"] or 0,
        "tasks_overdue": totals["tasks_overdue"] or 0,
        "tasks_pending": totals["tasks_pending"] or 0,
        "avg_completion_hours": round(avg_row["avg_hours"] or 0, 1) if avg_row else 0,
        "by_priority": by_priority,
        "by_employee": [
            {
                "name": r["name"],
                "assigned": r["assigned"],
                "completed": r["completed"],
                "overdue": r["overdue"],
                "avg_hours": round(r["avg_hours"] or 0, 1),
            }
            for r in emp_rows
        ],
        "token_usage_today": {
            "total_tokens": token_total,
            "total_cost_estimate": round(token_cost, 4),
            "by_provider": [
                {
                    "provider": r["provider"],
                    "tokens": r["tokens"] or 0,
                    "requests": r["requests"],
                    "cost": round(r["cost"] or 0, 4),
                }
                for r in token_rows
            ],
        },
    }
