import json
import logging

from app.core.database import db
from app.models.schemas import ClassifiedIntent, IntentType, InternalMessage
from app.services.llm_gateway import llm_gateway
from app.services.whatsapp_outbound import whatsapp

logger = logging.getLogger(__name__)

_TASK_EXTRACTION_PROMPT = """\
You are extracting task details from a WhatsApp message.
Given the message and recent conversation context, extract:
- assignee: the person being assigned the task (name only)
- description: what needs to be done (concise)
- priority: P0 (urgent), P1 (normal), or P2 (low)
- deadline: any mentioned deadline, or null

Respond with ONLY valid JSON:
{"assignee": "name", "description": "task", "priority": "P1", "deadline": null}
"""

_CONVERSATION_PROMPT = """\
You are NSI Bot, a helpful assistant for North Star Impex Group.
Keep responses brief and professional. You handle tasks, queries, and general \
coordination for the team via WhatsApp.
"""

_QUERY_PROMPT = """\
You are NSI Bot answering a data query for North Star Impex Group.
Use the provided database results to give a clear, concise natural language answer.
If the data is empty, say you couldn't find matching records.
"""


async def dispatch(message: InternalMessage, intent: ClassifiedIntent) -> None:
    handlers = {
        IntentType.GENERATE_DOCUMENT: _handle_generate_document,
        IntentType.ASSIGN_TASK: _handle_assign_task,
        IntentType.QUERY_DATA: _handle_query_data,
        IntentType.CHECK_STATUS: _handle_check_status,
        IntentType.CANCEL_TASK: _handle_cancel_task,
        IntentType.PAUSE_TASK: _handle_pause_task,
        IntentType.UPLOAD_FILE: _handle_upload_file,
        IntentType.COMPARE_FILES: _handle_compare_files,
        IntentType.RESEARCH: _handle_research,
        IntentType.GENERAL_CONVERSATION: _handle_conversation,
    }
    handler = handlers.get(intent.intent, _handle_conversation)
    try:
        await handler(message, intent)
    except Exception:
        logger.exception("Dispatch failed for intent=%s", intent.intent.value)
        await _send_error_reply(message.chat_id)

    await _check_buffer_done(message)


async def _get_recent_context(chat_id: str, limit: int = 10) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT sender_name, content, timestamp FROM messages "
        "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
        (chat_id, limit),
    )
    context = []
    for row in reversed(rows):
        role = "user"
        content = f"[{row['sender_name']}]: {row['content']}"
        context.append({"role": role, "content": content})
    return context


async def _handle_assign_task(message: InternalMessage, intent: ClassifiedIntent) -> None:
    from app.services.task_engine import create_task, resolve_employee

    context = await _get_recent_context(message.chat_id, limit=10)
    command = intent.raw_command or message.bot_command or message.content

    llm_messages = [
        {"role": "system", "content": _TASK_EXTRACTION_PROMPT},
        *context,
        {"role": "user", "content": f"Extract task from this command: {command}"},
    ]
    response = await llm_gateway.chat(llm_messages, max_tokens=500, request_type="dispatch:assign_task")
    raw = response.get("content", "")

    try:
        details = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Could not parse task details from LLM: %s", raw)
        await whatsapp.send_text(message.chat_id, "I couldn't understand the task details. Please try rephrasing.")
        return

    assignee_name = details.get("assignee") or intent.assignee
    if not assignee_name:
        await whatsapp.send_text(message.chat_id, "I need to know who to assign this task to. Please mention a name.")
        return

    assignee = await resolve_employee(assignee_name)
    if not assignee:
        await whatsapp.send_text(
            message.chat_id,
            f"I couldn't find an employee matching '{assignee_name}'. Please check the name.",
        )
        return

    assigner = await resolve_employee(message.sender_id)
    assigner_id = assigner["id"] if assigner else message.sender_id

    priority = details.get("priority", "P1")
    if priority not in ("P0", "P1", "P2"):
        priority = "P1"

    task = await create_task(
        assigner_id=assigner_id,
        assignee_id=assignee["id"],
        description=details.get("description", command),
        priority=priority,
        source_chat_id=message.chat_id,
        source_message_id=message.id,
        deadline=details.get("deadline") or intent.deadline,
    )

    deadline_text = f"\nDeadline: {task['deadline']}" if task.get("deadline") else ""
    await whatsapp.send_text(
        message.chat_id,
        f"✅ Task assigned to {assignee['name']}:\n"
        f"{task['description']}\n"
        f"Priority: {task['priority']}{deadline_text}",
    )


async def _handle_check_status(message: InternalMessage, intent: ClassifiedIntent) -> None:
    from app.services.task_engine import get_task_summary, resolve_employee

    target = intent.assignee
    assignee_id = None
    if target:
        emp = await resolve_employee(target)
        if emp:
            assignee_id = emp["id"]

    summary = await get_task_summary(assignee_id)
    await whatsapp.send_text(message.chat_id, summary)


async def _handle_cancel_task(message: InternalMessage, intent: ClassifiedIntent) -> None:
    from app.services.task_engine import cancel_task

    command = (intent.raw_command or message.bot_command or message.content).lower()
    task = await _find_task_by_description(message.chat_id, command)

    if not task:
        await whatsapp.send_text(message.chat_id, "I couldn't find a matching active task to cancel.")
        return

    success = await cancel_task(task["id"])
    if success:
        await whatsapp.send_text(message.chat_id, f"❌ Task cancelled: {task['description']}")
    else:
        await whatsapp.send_text(message.chat_id, "Failed to cancel the task. It may have already been completed.")


async def _handle_pause_task(message: InternalMessage, intent: ClassifiedIntent) -> None:
    from app.services.task_engine import pause_task

    command = (intent.raw_command or message.bot_command or message.content).lower()
    task = await _find_task_by_description(message.chat_id, command)

    if not task:
        await whatsapp.send_text(message.chat_id, "I couldn't find a matching active task to pause.")
        return

    success = await pause_task(task["id"])
    if success:
        await whatsapp.send_text(message.chat_id, f"⏸️ Task paused: {task['description']}")
    else:
        await whatsapp.send_text(message.chat_id, "Failed to pause the task.")


async def _handle_generate_document(message: InternalMessage, intent: ClassifiedIntent) -> None:
    from app.services.doc_generator import generate_document

    context = await _get_recent_context(message.chat_id, limit=15)
    command = intent.raw_command or message.bot_command or message.content
    await generate_document(message.chat_id, command, message.sender_id, context)


async def _handle_upload_file(message: InternalMessage, intent: ClassifiedIntent) -> None:
    if message.media_id:
        from app.services.file_handler import process_media_message
        await process_media_message(message)
    else:
        from app.services.context_buffer import open_buffer
        await open_buffer(
            message.sender_id,
            message.chat_id,
            "upload_file",
            message_id=message.id,
        )


async def _handle_query_data(message: InternalMessage, intent: ClassifiedIntent) -> None:
    command = intent.raw_command or message.bot_command or message.content

    entities = await db.fetch_all(
        "SELECT type, name, metadata FROM entities ORDER BY updated_at DESC LIMIT 20",
    )
    relationships = await db.fetch_all(
        "SELECT r.relation_type, e1.name AS source, e2.name AS target, r.metadata "
        "FROM relationships r "
        "JOIN entities e1 ON r.source_id = e1.id "
        "JOIN entities e2 ON r.target_id = e2.id "
        "ORDER BY r.created_at DESC LIMIT 20",
    )
    documents = await db.fetch_all(
        "SELECT filename, doc_type, project, description, created_at "
        "FROM documents ORDER BY created_at DESC LIMIT 10",
    )

    data_context = json.dumps({
        "entities": entities,
        "relationships": relationships,
        "documents": documents,
    }, default=str)

    context = await _get_recent_context(message.chat_id, limit=5)
    llm_messages = [
        {"role": "system", "content": _QUERY_PROMPT},
        *context,
        {"role": "user", "content": f"Query: {command}\n\nAvailable data:\n{data_context}"},
    ]

    response = await llm_gateway.chat(llm_messages, max_tokens=1000, request_type="dispatch:query_data")
    answer = response.get("content", "I couldn't find relevant data for that query.")
    await whatsapp.send_text(message.chat_id, answer)


async def _handle_compare_files(message: InternalMessage, intent: ClassifiedIntent) -> None:
    await whatsapp.send_text(message.chat_id, "File comparison coming soon.")


async def _handle_research(message: InternalMessage, intent: ClassifiedIntent) -> None:
    await whatsapp.send_text(message.chat_id, "Research feature coming in V2.")


async def _handle_conversation(message: InternalMessage, intent: ClassifiedIntent) -> None:
    context = await _get_recent_context(message.chat_id, limit=5)
    command = intent.raw_command or message.bot_command or message.content

    llm_messages = [
        {"role": "system", "content": _CONVERSATION_PROMPT},
        *context,
        {"role": "user", "content": command},
    ]

    response = await llm_gateway.chat(llm_messages, max_tokens=500, request_type="dispatch:conversation")
    reply = response.get("content", "I'm not sure how to help with that. Could you rephrase?")
    await whatsapp.send_text(message.chat_id, reply)


async def _check_buffer_done(message: InternalMessage) -> None:
    content = (message.content or "").strip().lower()
    if content not in ("done", "done.", "done!"):
        return

    from app.services.context_buffer import get_active_buffer, close_buffer

    buf = await get_active_buffer(message.sender_id, message.chat_id)
    if not buf:
        return

    closed = await close_buffer(buf["id"], status="complete")
    if closed:
        await whatsapp.send_text(
            message.chat_id,
            "Buffer closed. Processing your collected messages now.",
        )
        logger.info("Buffer %s closed by 'done' from %s", buf["id"], message.sender_name)


async def _send_error_reply(chat_id: str) -> None:
    try:
        await whatsapp.send_text(
            chat_id,
            "Sorry, I encountered an error processing that request. Please try again.",
        )
    except Exception:
        logger.exception("Failed to send error reply to %s", chat_id)


async def _find_task_by_description(chat_id: str, command: str) -> dict | None:
    tasks = await db.fetch_all(
        "SELECT * FROM tasks WHERE source_chat_id = ? "
        "AND status IN ('pending', 'nudged_1', 'nudged_2', 'escalated') "
        "ORDER BY created_at DESC",
        (chat_id,),
    )
    if not tasks:
        return None

    if len(tasks) == 1:
        return tasks[0]

    for task in tasks:
        desc_words = set(task["description"].lower().split())
        cmd_words = set(command.split())
        if desc_words & cmd_words:
            return task

    return tasks[0]
