import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.database import db
from app.core.queue import message_queue
from app.core.scheduler import start as start_scheduler, shutdown as shutdown_scheduler
from app.services.ingress import parse_webhook_payload, store_message

logger = logging.getLogger(__name__)


async def process_message(payload: dict):
    try:
        message = await parse_webhook_payload(payload)
        if message is None:
            return

        await store_message(message)

        from app.services.entity_extractor import extract_and_store
        await extract_and_store(message)

        if message.media_id:
            from app.services.file_handler import process_media_message
            await process_media_message(message)

        if message.is_bot_mention:
            from app.agents.router_agent import router_agent
            from app.services.dispatcher import dispatch
            intent = await router_agent.route(message)
            logger.info("Classified intent=%s confidence=%.2f for message=%s",
                        intent.intent.value, intent.confidence, message.id)
            await dispatch(message, intent)
        else:
            from app.services.context_buffer import add_to_buffer
            from app.services.task_engine import detect_completion
            from app.services.implicit_task_detector import detect_implicit_tasks

            buffer_result = await add_to_buffer(message.sender_id, message.chat_id, message_id=message.id)
            if buffer_result:
                logger.debug("Added message to active buffer for %s", message.sender_name)

            completed = await detect_completion(message.chat_id, message.sender_id, message.content)
            if completed:
                logger.info("Task auto-completed by message from %s", message.sender_name)

            await detect_implicit_tasks(message)

    except Exception:
        logger.exception("Error processing message payload")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from app.services.whatsapp_outbound import whatsapp

    await db.initialize()
    message_queue.set_handler(process_message)
    asyncio.create_task(message_queue.process_loop())
    await whatsapp.connect()
    start_scheduler()
    logger.info("NSI Bot started")

    yield

    shutdown_scheduler()
    await message_queue.shutdown()
    await whatsapp.disconnect()
    await db.close()
    logger.info("NSI Bot stopped")


app = FastAPI(title="NSI Bot", version="1.0.0", lifespan=lifespan)

from app.api.webhook import router as webhook_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.analytics import router as analytics_router
from app.api.chat import router as chat_router
from app.api.buffers import router as buffers_router
from app.api.upload import router as upload_router

app.include_router(webhook_router)
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(buffers_router)
app.include_router(upload_router)

static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(static_dir), html=True), name="dashboard")
