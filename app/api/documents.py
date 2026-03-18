import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.database import db
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/documents")
async def search_documents(
    q: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    _user: dict = Depends(get_current_user),
):
    clauses: list[str] = []
    params: list = []

    if q:
        clauses.append(
            "(filename LIKE ? OR description LIKE ? OR project LIKE ? OR doc_type LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if project:
        clauses.append("project = ?")
        params.append(project)
    if doc_type:
        clauses.append("doc_type = ?")
        params.append(doc_type)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = await db.fetch_all(
        f"SELECT * FROM documents{where} ORDER BY created_at DESC LIMIT ?",
        tuple(params),
    )
    return rows
