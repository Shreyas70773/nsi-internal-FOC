import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.database import db

router = APIRouter()
logger = logging.getLogger(__name__)


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None


@router.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
):
    clauses: list[str] = []
    params: list[str] = []

    if status:
        clauses.append("t.status = ?")
        params.append(status)
    if assignee_id:
        clauses.append("t.assignee_id = ?")
        params.append(assignee_id)
    if priority:
        clauses.append("t.priority = ?")
        params.append(priority)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT t.*, "
        "  e1.name AS assigner_name, "
        "  e2.name AS assignee_name "
        "FROM tasks t "
        "LEFT JOIN employees e1 ON t.assigner_id = e1.id "
        "LEFT JOIN employees e2 ON t.assignee_id = e2.id"
        f"{where} ORDER BY t.created_at DESC"
    )
    rows = await db.fetch_all(sql, tuple(params))
    return rows


@router.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    existing = await db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    updates: list[str] = []
    params: list[str] = []

    if body.status is not None:
        updates.append("status = ?")
        params.append(body.status)
    if body.priority is not None:
        updates.append("priority = ?")
        params.append(body.priority)
    if body.assignee_id is not None:
        updates.append("assignee_id = ?")
        params.append(body.assignee_id)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(task_id)

    sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    await db.execute(sql, tuple(params))

    updated = await db.fetch_one(
        "SELECT t.*, "
        "  e1.name AS assigner_name, "
        "  e2.name AS assignee_name "
        "FROM tasks t "
        "LEFT JOIN employees e1 ON t.assigner_id = e1.id "
        "LEFT JOIN employees e2 ON t.assignee_id = e2.id "
        "WHERE t.id = ?",
        (task_id,),
    )
    logger.info("Task %s updated: %s", task_id, body.model_dump(exclude_none=True))
    return updated
