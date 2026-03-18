import asyncio
import json
import logging
import time

import websockets

from app.config import settings

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 2.0


class WhatsAppOutbound:
    def __init__(self) -> None:
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._last_send_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            headers = {}
            if settings.openclaw_api_key:
                headers["Authorization"] = f"Bearer {settings.openclaw_api_key}"
            self._ws = await websockets.connect(
                settings.openclaw_ws_url,
                additional_headers=headers,
            )
            logger.info("Connected to OpenClaw gateway at %s", settings.openclaw_ws_url)
        except Exception:
            logger.warning(
                "Could not connect to OpenClaw at %s — messages will be logged only",
                settings.openclaw_ws_url,
            )
            self._ws = None

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            logger.info("Disconnected from OpenClaw gateway")

    async def _enforce_rate_limit(self, chat_id: str) -> None:
        now = time.monotonic()
        last = self._last_send_at.get(chat_id, 0.0)
        gap = RATE_LIMIT_SECONDS - (now - last)
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_send_at[chat_id] = time.monotonic()

    async def _send_payload(self, payload: dict) -> bool:
        chat_id = payload.get("to", "")
        await self._enforce_rate_limit(chat_id)

        async with self._lock:
            if self._ws is None:
                logger.info("[DRY-RUN] Would send to %s: %s", chat_id, json.dumps(payload))
                return True
            try:
                await self._ws.send(json.dumps(payload))
                logger.debug("Sent payload to %s", chat_id)
                return True
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection lost — attempting reconnect")
                await self.connect()
                if self._ws:
                    try:
                        await self._ws.send(json.dumps(payload))
                        return True
                    except Exception:
                        logger.exception("Retry send failed for %s", chat_id)
                        return False
                logger.info("[DRY-RUN] Would send to %s: %s", chat_id, json.dumps(payload))
                return True
            except Exception:
                logger.exception("Failed to send message to %s", chat_id)
                return False

    async def send_text(self, chat_id: str, text: str) -> bool:
        payload = {
            "action": "send",
            "channel": "whatsapp",
            "to": chat_id,
            "type": "text",
            "content": text,
        }
        return await self._send_payload(payload)

    async def send_document(
        self, chat_id: str, file_path: str, filename: str, caption: str = ""
    ) -> bool:
        payload = {
            "action": "send",
            "channel": "whatsapp",
            "to": chat_id,
            "type": "document",
            "media_path": file_path,
            "media_filename": filename,
            "content": caption,
        }
        return await self._send_payload(payload)


whatsapp = WhatsAppOutbound()
