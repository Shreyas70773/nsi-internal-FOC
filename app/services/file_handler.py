import asyncio
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import db, new_id
from app.models.schemas import InternalMessage
from app.services.drive_sync import drive_client
from app.services.llm_gateway import llm_gateway
from app.services.whatsapp_outbound import whatsapp

logger = logging.getLogger(__name__)

TEMP_DIR = Path(tempfile.gettempdir()) / "drive_sync"


async def process_media_message(message: InternalMessage) -> None:
    if not message.media_id:
        return

    filename = message.media_filename or f"file_{message.media_id}"
    doc_id = new_id()

    await db.execute(
        "INSERT INTO documents (id, filename, mime_type, source_chat_id, "
        "source_message_id, uploaded_by, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending_upload', datetime('now'))",
        (doc_id, filename, message.media_mime, message.chat_id,
         message.id, message.sender_name),
    )

    local_path = await download_media(message.media_id, filename)
    if not local_path:
        logger.warning("Media download unavailable for %s — skipping pipeline", message.media_id)
        await db.execute(
            "UPDATE documents SET status = 'download_failed' WHERE id = ?",
            (doc_id,),
        )
        return

    try:
        file_hash = await _compute_hash(local_path)
        await db.execute(
            "UPDATE documents SET file_hash = ?, file_size_bytes = ?, local_path = ? WHERE id = ?",
            (file_hash, os.path.getsize(local_path), local_path, doc_id),
        )

        duplicate = await db.fetch_one(
            "SELECT id, drive_url, folder_path FROM documents "
            "WHERE file_hash = ? AND id != ? AND status = 'uploaded' LIMIT 1",
            (file_hash, doc_id),
        )
        if duplicate:
            await db.execute(
                "UPDATE documents SET duplicate_of = ?, status = 'duplicate' WHERE id = ?",
                (duplicate["id"], doc_id),
            )
            await whatsapp.send_text(
                message.chat_id,
                f"Duplicate detected: {filename} already filed at {duplicate['folder_path']}",
            )
            return

        classification = await categorize_file(
            filename, message.sender_name, message.content or ""
        )
        project = classification.get("project", "_Unsorted")
        subfolder = classification.get("subfolder", "Miscellaneous")
        doc_type = classification.get("doc_type", "unknown")
        description = classification.get("description", "")

        folders = await drive_client.bootstrap_folder_structure()
        if not folders:
            logger.error("Drive folder structure unavailable — cannot upload")
            await db.execute(
                "UPDATE documents SET status = 'upload_failed' WHERE id = ?",
                (doc_id,),
            )
            return

        folder_path = f"Projects/{project}" if project != "_Unsorted" else "Projects/_Unsorted"
        target_folder_id = folders.get(folder_path)

        if not target_folder_id:
            target_folder_id = await drive_client.ensure_folder(
                project,
                folders.get("Projects", folders.get("Projects/_Unsorted")),
            )
            if target_folder_id and subfolder:
                sub_id = await drive_client.ensure_folder(subfolder, target_folder_id)
                if sub_id:
                    target_folder_id = sub_id
                    folder_path = f"Projects/{project}/{subfolder}"

        if not target_folder_id:
            target_folder_id = folders.get("Projects/_Unsorted")
            folder_path = "Projects/_Unsorted"

        await db.execute(
            "UPDATE documents SET project = ?, doc_type = ?, description = ?, folder_path = ? "
            "WHERE id = ?",
            (project, doc_type, description, folder_path, doc_id),
        )

        success = await upload_with_retry(
            local_path, filename, target_folder_id, doc_id,
            message.chat_id, message.media_mime,
        )

        if success:
            await whatsapp.send_text(
                message.chat_id,
                f"Filed: {filename} → {folder_path} ✓",
            )

    except Exception:
        logger.exception("Error processing media message %s", message.id)
        await db.execute(
            "UPDATE documents SET status = 'upload_failed' WHERE id = ?",
            (doc_id,),
        )
    finally:
        if local_path and Path(local_path).exists():
            try:
                os.unlink(local_path)
            except OSError:
                pass


async def download_media(media_id: str, filename: str | None = None) -> str | None:
    logger.info(
        "Media download requested: media_id=%s filename=%s — "
        "placeholder (OpenClaw media endpoint not yet wired)",
        media_id, filename,
    )
    return None


async def categorize_file(filename: str, sender_name: str, chat_context: str) -> dict:
    try:
        entities = await db.fetch_all(
            "SELECT DISTINCT name FROM entities WHERE type = 'company' LIMIT 50"
        )
        known_projects = [e["name"] for e in entities] if entities else []
    except Exception:
        known_projects = []

    prompt = (
        f"Given filename '{filename}' sent by '{sender_name}' in context: '{chat_context}'. "
        f"Classify into: {{project: str, subfolder: str, doc_type: str, description: str}}. "
        f"Available projects: {known_projects or 'none known — use _Unsorted'}. "
        f"Return JSON only."
    )

    try:
        result = await llm_gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
            request_type="file_categorization",
        )
        content = result.get("content", "")
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(content)
    except (json.JSONDecodeError, RuntimeError):
        logger.warning("LLM categorization failed for '%s', using defaults", filename)
        return {
            "project": "_Unsorted",
            "subfolder": "Miscellaneous",
            "doc_type": "unknown",
            "description": filename,
        }


async def upload_with_retry(
    local_path: str,
    filename: str,
    folder_id: str,
    doc_id: str,
    chat_id: str,
    mime_type: str | None = None,
    max_retries: int = 3,
) -> bool:
    backoff = 0.4

    for attempt in range(1, max_retries + 1):
        try:
            result = await drive_client.upload_file(local_path, filename, folder_id, mime_type)
            if result:
                await db.execute(
                    "UPDATE documents SET status = 'uploaded', drive_url = ?, "
                    "drive_file_id = ? WHERE id = ?",
                    (result["web_view_link"], result["file_id"], doc_id),
                )
                if Path(local_path).exists():
                    os.unlink(local_path)
                return True
        except Exception:
            logger.warning(
                "Upload attempt %d/%d failed for %s",
                attempt, max_retries, filename, exc_info=True,
            )

        if attempt < max_retries:
            await asyncio.sleep(backoff)
            backoff *= 4

    await db.execute(
        "UPDATE documents SET status = 'upload_failed', "
        "retry_count = COALESCE(retry_count, 0) + ? WHERE id = ?",
        (max_retries, doc_id),
    )
    await whatsapp.send_text(
        chat_id,
        f"⚠ Upload failed after {max_retries} attempts: {filename}",
    )
    return False


async def retry_failed_uploads() -> int:
    rows = await db.fetch_all(
        "SELECT id, local_path, filename, folder_path, source_chat_id, mime_type "
        "FROM documents WHERE status = 'upload_failed' AND retry_count < 5"
    )
    if not rows:
        return 0

    folders = await drive_client.bootstrap_folder_structure()
    if not folders:
        logger.error("Drive folder structure unavailable — cannot retry uploads")
        return 0

    success_count = 0
    for row in rows:
        local_path = row.get("local_path")
        if not local_path or not Path(local_path).exists():
            logger.debug("Skipping retry for %s — local file missing", row["id"])
            continue

        folder_path = row.get("folder_path", "Projects/_Unsorted")
        folder_id = folders.get(folder_path, folders.get("Projects/_Unsorted"))
        if not folder_id:
            continue

        ok = await upload_with_retry(
            local_path,
            row["filename"],
            folder_id,
            row["id"],
            row.get("source_chat_id", ""),
            row.get("mime_type"),
            max_retries=1,
        )
        if ok:
            success_count += 1

    logger.info("Retry cycle complete: %d/%d uploads succeeded", success_count, len(rows))
    return success_count


async def _compute_hash(file_path: str) -> str:
    loop = asyncio.get_event_loop()

    def _sha256() -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    return await loop.run_in_executor(None, _sha256)
