import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self) -> None:
        self._db_path = settings.db_path
        self._conn: aiosqlite.Connection | None = None
        self._write_queue: asyncio.Queue[tuple[str, tuple, asyncio.Future]] = asyncio.Queue()
        self._writer_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        await self._ensure_schema_version_table()
        await self._run_migrations()

        self._writer_task = asyncio.get_event_loop().create_task(self._write_loop())
        logger.info("Database initialized at %s", self._db_path)

    async def _ensure_schema_version_table(self) -> None:
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "  filename TEXT PRIMARY KEY,"
            "  applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        await self._conn.commit()

    async def _run_migrations(self) -> None:
        if not _MIGRATIONS_DIR.is_dir():
            logger.warning("Migrations directory not found: %s", _MIGRATIONS_DIR)
            return

        applied: set[str] = set()
        async with self._conn.execute("SELECT filename FROM schema_version") as cursor:
            async for row in cursor:
                applied.add(row[0])

        sql_files = sorted(
            f for f in _MIGRATIONS_DIR.iterdir()
            if f.suffix == ".sql" and f.name not in applied
        )

        for sql_file in sql_files:
            logger.info("Applying migration: %s", sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            await self._conn.executescript(sql)
            await self._conn.execute(
                "INSERT INTO schema_version (filename) VALUES (?)",
                (sql_file.name,),
            )
            await self._conn.commit()
            logger.info("Migration applied: %s", sql_file.name)

    async def _write_loop(self) -> None:
        """Serialized writer — all mutating queries flow through here to avoid SQLITE_BUSY."""
        while True:
            sql, params, future = await self._write_queue.get()
            try:
                await self._conn.execute(sql, params)
                await self._conn.commit()
                future.set_result(None)
            except Exception as exc:
                future.set_exception(exc)
            finally:
                self._write_queue.task_done()

    async def execute(self, sql: str, params: tuple = ()) -> None:
        loop = asyncio.get_event_loop()
        future: asyncio.Future[None] = loop.create_future()
        await self._write_queue.put((sql, params, future))
        await future

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._writer_task:
            if not self._write_queue.empty():
                await self._write_queue.join()
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
        if self._conn:
            await self._conn.close()
        logger.info("Database connection closed")


def new_id() -> str:
    return uuid.uuid4().hex


db = Database()
