import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)


async def _chaser_tick() -> None:
    try:
        from app.services.chaser import chaser_tick
        await chaser_tick()
    except Exception:
        logger.exception("Chaser tick failed")


async def _db_backup() -> None:
    src = Path(settings.db_path)
    if not src.exists():
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = src.parent / f"nsi_backup_{ts}.db"
    try:
        shutil.copy2(str(src), str(dst))
        logger.info("DB backup created: %s", dst.name)
        backups = sorted(src.parent.glob("nsi_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[5:]:
            old.unlink(missing_ok=True)
    except Exception:
        logger.exception("Local DB backup failed")

    try:
        from app.services.drive_sync import drive_client
        await drive_client.backup_database()
    except Exception:
        logger.exception("Drive DB backup failed")


async def _buffer_timeout_check() -> None:
    try:
        from app.services.context_buffer import check_timeouts
        timed_out = await check_timeouts()
        if timed_out:
            logger.info("Buffer timeout check: %d buffers timed out", len(timed_out))
    except Exception:
        logger.exception("Buffer timeout check failed")


async def _eod_report() -> None:
    try:
        from app.services.eod_report import generate_eod_report
        await generate_eod_report()
    except Exception:
        logger.exception("EOD report generation failed")


async def _weekly_summary() -> None:
    try:
        from app.services.eod_report import generate_weekly_summary
        await generate_weekly_summary()
    except Exception:
        logger.exception("Weekly summary generation failed")


async def _retry_failed_uploads() -> None:
    try:
        from app.services.file_handler import retry_failed_uploads
        count = await retry_failed_uploads()
        if count:
            logger.info("Retried uploads: %d succeeded", count)
    except Exception:
        logger.exception("Retry failed uploads job failed")


async def _log_rotation() -> None:
    logger.info("Log rotation job fired (placeholder)")


async def _heartbeat() -> None:
    try:
        from app.services.whatsapp_outbound import whatsapp
        from app.core.database import db

        row = await db.fetch_one(
            "SELECT DISTINCT chat_id FROM messages "
            "WHERE chat_type='group' ORDER BY timestamp DESC LIMIT 1"
        )
        if row:
            await whatsapp.send_text(row["chat_id"], "🤖 NSI Bot is online and healthy.")
        logger.debug("Heartbeat OK")
    except Exception:
        logger.exception("Heartbeat failed")


async def _idempotency_cleanup() -> None:
    try:
        from app.services.ingress import cleanup_idempotency
        await cleanup_idempotency()
    except Exception:
        logger.exception("Idempotency cleanup failed")


scheduler = AsyncIOScheduler()


def setup_jobs() -> None:
    scheduler.add_job(_chaser_tick, "interval", minutes=settings.chaser_interval_minutes, id="chaser_tick")
    scheduler.add_job(_db_backup, "interval", minutes=60, id="db_backup")
    scheduler.add_job(_buffer_timeout_check, "interval", minutes=1, id="buffer_timeout_check")
    scheduler.add_job(
        _eod_report,
        "cron",
        hour=18,
        minute=0,
        timezone="Asia/Kolkata",
        id="eod_report",
    )
    scheduler.add_job(
        _weekly_summary,
        "cron",
        day_of_week="sun",
        hour=18,
        minute=0,
        timezone="Asia/Kolkata",
        id="weekly_summary",
    )
    scheduler.add_job(_retry_failed_uploads, "interval", minutes=30, id="retry_failed_uploads")
    scheduler.add_job(
        _log_rotation,
        "cron",
        hour=3,
        minute=0,
        id="log_rotation",
    )
    scheduler.add_job(_heartbeat, "interval", minutes=60, id="heartbeat")
    scheduler.add_job(_idempotency_cleanup, "interval", minutes=30, id="idempotency_cleanup")
    logger.info("Scheduled %d jobs", len(scheduler.get_jobs()))


def start() -> None:
    setup_jobs()
    scheduler.start()
    logger.info("Scheduler started")


def shutdown() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")
