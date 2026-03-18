import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

FOLDER_HIERARCHY = [
    "Projects/_Unsorted",
    "General/Payment_Records",
    "General/Company_Documents",
    "General/Miscellaneous",
    "Generated_Documents/Proforma_Invoices",
    "Generated_Documents/Commercial_Quotations",
    "Generated_Documents/Packing_Lists",
    "Chat_Backups/Daily_Summaries",
    "System/DB_Backups",
    "System/Logs",
]

MAX_DB_BACKUPS = 10


class DriveClient:
    def __init__(self) -> None:
        self._service = None
        self._initialized = False
        self._folder_cache: dict[str, str] | None = None

    def _ensure_init(self) -> bool:
        if self._initialized:
            return self._service is not None
        self._initialized = True

        sa_path = settings.google_service_account_json
        if not sa_path or not Path(sa_path).exists():
            logger.warning(
                "Google Service Account JSON not found at '%s' — Drive sync disabled",
                sa_path,
            )
            return False

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_service_account_file(
                sa_path,
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            self._service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive client initialized")
            return True
        except Exception:
            logger.exception("Failed to initialize Google Drive client")
            return False

    def _find_folder_sync(self, name: str, parent_id: str) -> str | None:
        query = (
            f"name = '{name}' and '{parent_id}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        resp = self._service.files().list(
            q=query, spaces="drive", fields="files(id)", pageSize=1
        ).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    def _create_folder_sync(self, name: str, parent_id: str) -> str:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = self._service.files().create(
            body=metadata, fields="id"
        ).execute()
        return folder["id"]

    async def ensure_folder(self, name: str, parent_id: str | None = None) -> str | None:
        if not self._ensure_init():
            return None

        parent_id = parent_id or settings.google_drive_root_folder_id
        loop = asyncio.get_event_loop()

        existing = await loop.run_in_executor(
            None, self._find_folder_sync, name, parent_id
        )
        if existing:
            return existing

        return await loop.run_in_executor(
            None, self._create_folder_sync, name, parent_id
        )

    async def upload_file(
        self,
        local_path: str,
        filename: str,
        folder_id: str,
        mime_type: str | None = None,
    ) -> dict | None:
        if not self._ensure_init():
            return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._upload_file_sync, local_path, filename, folder_id, mime_type
        )

    def _upload_file_sync(
        self, local_path: str, filename: str, folder_id: str, mime_type: str | None
    ) -> dict:
        from googleapiclient.http import MediaFileUpload

        file_size = os.path.getsize(local_path)
        resumable = file_size > 5 * 1024 * 1024

        media = MediaFileUpload(
            local_path,
            mimetype=mime_type or "application/octet-stream",
            resumable=resumable,
        )
        metadata = {"name": filename, "parents": [folder_id]}

        uploaded = self._service.files().create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        return {
            "file_id": uploaded["id"],
            "web_view_link": uploaded.get("webViewLink", ""),
        }

    async def bootstrap_folder_structure(self) -> dict[str, str] | None:
        if not self._ensure_init():
            return None

        if self._folder_cache is not None:
            return self._folder_cache

        root_id = settings.google_drive_root_folder_id
        if not root_id:
            logger.error("google_drive_root_folder_id is not set")
            return None

        folder_map: dict[str, str] = {}

        for path in FOLDER_HIERARCHY:
            parts = path.split("/")
            current_parent = root_id
            built_path = ""

            for part in parts:
                built_path = f"{built_path}/{part}" if built_path else part
                if built_path in folder_map:
                    current_parent = folder_map[built_path]
                    continue

                folder_id = await self.ensure_folder(part, current_parent)
                if folder_id is None:
                    logger.error("Failed to create folder '%s'", built_path)
                    return None
                folder_map[built_path] = folder_id
                current_parent = folder_id

        self._folder_cache = folder_map
        logger.info("Drive folder structure bootstrapped: %d folders", len(folder_map))
        return folder_map

    async def backup_database(self) -> bool:
        if not self._ensure_init():
            return False

        folders = await self.bootstrap_folder_structure()
        if not folders or "System/DB_Backups" not in folders:
            logger.error("Cannot backup — folder structure not available")
            return False

        backup_folder_id = folders["System/DB_Backups"]
        db_path = Path(settings.db_path)
        if not db_path.exists():
            logger.error("Database file not found at %s", db_path)
            return False

        tmp_dir = Path(tempfile.gettempdir()) / "drive_sync"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = f"nsi_backup_{ts}.db"
        tmp_path = tmp_dir / backup_name

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, shutil.copy2, str(db_path), str(tmp_path)
            )

            result = await self.upload_file(
                str(tmp_path), backup_name, backup_folder_id, "application/x-sqlite3"
            )
            if not result:
                return False

            await self._prune_old_backups(backup_folder_id)

            logger.info("Database backup uploaded: %s", backup_name)
            return True
        except Exception:
            logger.exception("Database backup failed")
            return False
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    async def _prune_old_backups(self, folder_id: str) -> None:
        loop = asyncio.get_event_loop()

        def _list_backups() -> list[dict]:
            query = (
                f"'{folder_id}' in parents and trashed = false "
                f"and name contains 'nsi_backup_'"
            )
            resp = self._service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name, createdTime)",
                orderBy="createdTime desc",
                pageSize=100,
            ).execute()
            return resp.get("files", [])

        files = await loop.run_in_executor(None, _list_backups)

        if len(files) <= MAX_DB_BACKUPS:
            return

        to_delete = files[MAX_DB_BACKUPS:]
        for f in to_delete:
            try:
                await loop.run_in_executor(
                    None,
                    lambda fid=f["id"]: self._service.files().delete(fileId=fid).execute(),
                )
                logger.debug("Deleted old backup: %s", f["name"])
            except Exception:
                logger.warning("Failed to delete old backup %s", f["name"])


drive_client = DriveClient()
