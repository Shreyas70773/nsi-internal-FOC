import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.database import db, new_id
from app.api.auth import get_current_user
from app.services.file_handler import categorize_file

logger = logging.getLogger(__name__)
router = APIRouter()

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "nsi_uploads"


async def _hash_file(path: str) -> str:
    def _sha256():
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    return await asyncio.get_event_loop().run_in_executor(None, _sha256)


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = file.filename or f"upload_{new_id()[:8]}"
    local_path = str(_UPLOAD_DIR / f"{new_id()}_{filename}")

    try:
        content = await file.read()
        with open(local_path, "wb") as f:
            f.write(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    doc_id = new_id()
    file_hash = await _hash_file(local_path)
    file_size = os.path.getsize(local_path)

    await db.execute(
        "INSERT INTO documents "
        "(id, filename, mime_type, file_hash, file_size_bytes, uploaded_by, "
        "local_path, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_upload', datetime('now'))",
        (doc_id, filename, file.content_type, file_hash, file_size,
         user["id"], local_path),
    )

    classification = await categorize_file(filename, user["name"], "")
    project = classification.get("project", "_Unsorted")
    doc_type = classification.get("doc_type", "unknown")
    description = classification.get("description", "")
    folder_path = f"Projects/{project}" if project != "_Unsorted" else "Projects/_Unsorted"

    await db.execute(
        "UPDATE documents SET project = ?, doc_type = ?, description = ?, folder_path = ? WHERE id = ?",
        (project, doc_type, description, folder_path, doc_id),
    )

    drive_url = None
    try:
        from app.services.drive_sync import drive_client
        from app.services.file_handler import upload_with_retry

        folders = await drive_client.bootstrap_folder_structure()
        if folders:
            target_id = folders.get(folder_path, folders.get("Projects/_Unsorted"))
            if target_id:
                ok = await upload_with_retry(
                    local_path, filename, target_id, doc_id, "", file.content_type,
                )
                if ok:
                    doc = await db.fetch_one(
                        "SELECT drive_url FROM documents WHERE id = ?", (doc_id,),
                    )
                    drive_url = doc["drive_url"] if doc else None
    except Exception:
        logger.exception("Drive upload failed for %s", filename)

    doc = await db.fetch_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    logger.info("File uploaded: %s (%s) by %s", filename, doc_id, user["name"])

    return {
        "id": doc_id,
        "filename": filename,
        "drive_url": drive_url,
        "project": project,
        "doc_type": doc_type,
        "status": doc["status"] if doc else "pending_upload",
    }
