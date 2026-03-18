import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import db
from app.api.auth import get_current_user
from app.services.context_buffer import close_buffer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/buffers")
async def list_buffers(
    status: Optional[str] = Query(None),
    _user: dict = Depends(get_current_user),
):
    if status:
        rows = await db.fetch_all(
            "SELECT * FROM context_buffers WHERE status = ? ORDER BY last_activity_at DESC",
            (status,),
        )
    else:
        rows = await db.fetch_all(
            "SELECT * FROM context_buffers ORDER BY last_activity_at DESC"
        )
    return rows


@router.post("/api/buffers/{buffer_id}/trigger")
async def trigger_buffer(buffer_id: str, _user: dict = Depends(get_current_user)):
    buf = await db.fetch_one(
        "SELECT * FROM context_buffers WHERE id = ?", (buffer_id,),
    )
    if not buf:
        raise HTTPException(status_code=404, detail="Buffer not found")

    if buf["status"] not in ("collecting", "timed_out"):
        raise HTTPException(
            status_code=400,
            detail=f"Buffer cannot be triggered from status '{buf['status']}'",
        )

    result = await close_buffer(buffer_id, status="processing")
    logger.info("Buffer %s manually triggered by dashboard", buffer_id)
    return result


@router.delete("/api/buffers/{buffer_id}")
async def cancel_buffer(buffer_id: str, _user: dict = Depends(get_current_user)):
    buf = await db.fetch_one(
        "SELECT * FROM context_buffers WHERE id = ?", (buffer_id,),
    )
    if not buf:
        raise HTTPException(status_code=404, detail="Buffer not found")

    result = await close_buffer(buffer_id, status="complete")
    logger.info("Buffer %s cancelled via dashboard", buffer_id)
    return result
