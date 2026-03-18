import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import db, new_id
from app.api.auth import get_current_user
from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)
router = APIRouter()

_DASHBOARD_SYSTEM_PROMPT = (
    "You are NSI Bot, a professional assistant for North Star Impex Group. "
    "You help employees manage tasks, find documents, answer questions about ongoing projects, "
    "and provide general business assistance. Keep responses concise and helpful. "
    "Format responses for readability using short paragraphs. Do not use markdown headers."
)


class ChatRequest(BaseModel):
    message: str


@router.post("/api/chat")
async def send_chat(body: ChatRequest, user: dict = Depends(get_current_user)):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    chat_id = f"dashboard:{user['id']}"
    now = datetime.now(timezone.utc).isoformat()

    user_msg_id = new_id()
    await db.execute(
        "INSERT INTO messages (id, chat_id, chat_type, sender_id, sender_name, "
        "timestamp, type, content, created_at) VALUES (?, ?, 'dm', ?, ?, ?, 'text', ?, ?)",
        (user_msg_id, chat_id, user["id"], user["name"], now, body.message, now),
    )

    history = await db.fetch_all(
        "SELECT sender_id, content FROM messages "
        "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 20",
        (chat_id,),
    )

    messages = [{"role": "system", "content": _DASHBOARD_SYSTEM_PROMPT}]
    for row in reversed(history):
        role = "assistant" if row["sender_id"] == "nsi-bot" else "user"
        messages.append({"role": role, "content": row["content"]})

    try:
        result = await llm_gateway.chat(
            messages=messages, max_tokens=1000, request_type="dashboard:chat",
        )
        reply = result.get("content") or "I'm having trouble processing that. Please try again."
    except Exception:
        logger.exception("Dashboard chat LLM call failed")
        reply = "I'm temporarily unavailable. Please try again in a moment."

    bot_now = datetime.now(timezone.utc).isoformat()
    bot_msg_id = new_id()
    await db.execute(
        "INSERT INTO messages (id, chat_id, chat_type, sender_id, sender_name, "
        "timestamp, type, content, created_at) VALUES (?, ?, 'dm', 'nsi-bot', 'NSI Bot', ?, 'text', ?, ?)",
        (bot_msg_id, chat_id, bot_now, reply, bot_now),
    )

    return {"reply": reply, "message_id": bot_msg_id}


@router.get("/api/chat/history")
async def chat_history(user: dict = Depends(get_current_user)):
    chat_id = f"dashboard:{user['id']}"
    rows = await db.fetch_all(
        "SELECT id, sender_id, sender_name, content, timestamp FROM messages "
        "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 50",
        (chat_id,),
    )
    return list(reversed(rows))
