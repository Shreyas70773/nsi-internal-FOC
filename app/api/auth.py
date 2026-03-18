import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.database import db, new_id
from app.config import settings

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

logger = logging.getLogger(__name__)
router = APIRouter()

_USERS_FILE = Path(__file__).parent.parent.parent / "config" / "users.json"


def _load_users() -> list[dict]:
    if not _USERS_FILE.exists():
        return []
    with open(_USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("users", [])


def _is_bcrypt_hash(value: str) -> bool:
    return value.startswith(("$2b$", "$2a$", "$2y$"))


def _verify_password(stored: str, provided: str) -> bool:
    if _is_bcrypt_hash(stored):
        if not _HAS_BCRYPT:
            logger.warning("bcrypt not installed; cannot verify hashed password")
            return False
        return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
    # Dev mode: non-bcrypt entries accept any password
    return True


class LoginRequest(BaseModel):
    username: str
    password: str


class LogoutRequest(BaseModel):
    token: str


async def _resolve_or_create_employee(user: dict) -> dict:
    whatsapp_id = user.get("whatsapp_id", "")
    if whatsapp_id:
        employee = await db.fetch_one(
            "SELECT * FROM employees WHERE whatsapp_id = ?", (whatsapp_id,),
        )
        if employee:
            return employee

    employee = await db.fetch_one(
        "SELECT * FROM employees WHERE LOWER(name) = ?", (user["name"].lower(),),
    )
    if employee:
        return employee

    emp_id = new_id()
    await db.execute(
        "INSERT INTO employees (id, whatsapp_id, name, role, email) VALUES (?, ?, ?, ?, ?)",
        (emp_id, whatsapp_id, user["name"], user.get("role", "employee"), user.get("email", "")),
    )
    return await db.fetch_one("SELECT * FROM employees WHERE id = ?", (emp_id,))


@router.post("/api/auth/login")
async def login(body: LoginRequest):
    users = _load_users()
    user = next((u for u in users if u["username"] == body.username), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(user["password"], body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    employee = await _resolve_or_create_employee(user)

    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=settings.dashboard_session_hours)

    await db.execute(
        "INSERT INTO dashboard_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, employee["id"], now.isoformat(), expires.isoformat()),
    )

    logger.info("Dashboard login: %s (%s)", user["username"], user.get("role"))
    return {
        "token": token,
        "user": {
            "id": employee["id"],
            "name": user["name"],
            "role": user.get("role", "employee"),
            "username": user["username"],
        },
    }


@router.post("/api/auth/logout")
async def logout(body: LogoutRequest):
    await db.execute("DELETE FROM dashboard_sessions WHERE token = ?", (body.token,))
    return {"status": "ok"}


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth[7:]
    session = await db.fetch_one(
        "SELECT * FROM dashboard_sessions WHERE token = ?", (token,),
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if session.get("expires_at"):
        try:
            expires = datetime.fromisoformat(session["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                await db.execute("DELETE FROM dashboard_sessions WHERE token = ?", (token,))
                raise HTTPException(status_code=401, detail="Session expired")
        except ValueError:
            pass

    employee = await db.fetch_one(
        "SELECT * FROM employees WHERE id = ?", (session["user_id"],),
    )
    if not employee:
        raise HTTPException(status_code=401, detail="User not found")

    users = _load_users()
    cfg = next((u for u in users if u["name"] == employee["name"]), None)

    return {
        "id": employee["id"],
        "name": employee["name"],
        "role": cfg["role"] if cfg else employee.get("role", "employee"),
        "username": cfg["username"] if cfg else employee["name"].lower(),
        "email": employee.get("email", ""),
    }
