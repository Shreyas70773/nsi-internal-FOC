import logging
import shutil
import time
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.core.database import db
from app.models.schemas import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.time()


@router.get("/api/health")
async def health_check() -> HealthResponse:
    uptime = time.time() - _start_time

    db_file = Path(settings.db_path)
    db_size_mb = db_file.stat().st_size / (1024 * 1024) if db_file.exists() else 0.0

    disk = shutil.disk_usage(db_file.parent if db_file.parent.exists() else ".")
    disk_free_mb = disk.free / (1024 * 1024)

    try:
        row = await db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE status IN ('pending', 'nudged_1', 'nudged_2')"
        )
        tasks_pending = row["cnt"] if row else 0
    except Exception:
        logger.exception("Failed to query pending tasks")
        tasks_pending = -1

    try:
        row = await db.fetch_one("SELECT MAX(created_at) AS last_at FROM messages")
        last_message_at = row["last_at"] if row else None
    except Exception:
        logger.exception("Failed to query last message time")
        last_message_at = None

    return HealthResponse(
        status="healthy",
        uptime_seconds=round(uptime, 1),
        db_size_mb=round(db_size_mb, 2),
        disk_free_mb=round(disk_free_mb, 1),
        tasks_pending=tasks_pending,
        last_message_at=last_message_at,
        last_backup_at="N/A",
    )
