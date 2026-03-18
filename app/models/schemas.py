"""Pydantic models for all data types flowing through the system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChatType(str, Enum):
    GROUP = "group"
    DM = "dm"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACT = "contact"
    SYSTEM = "system"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class TaskPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TaskStatus(str, Enum):
    PENDING = "pending"
    NUDGED_1 = "nudged_1"
    NUDGED_2 = "nudged_2"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BufferStatus(str, Enum):
    COLLECTING = "collecting"
    TIMED_OUT = "timed_out"
    PROCESSING = "processing"
    COMPLETE = "complete"


class DocApprovalStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class IntentType(str, Enum):
    GENERATE_DOCUMENT = "generate_document"
    ASSIGN_TASK = "assign_task"
    QUERY_DATA = "query_data"
    COMPARE_FILES = "compare_files"
    CHECK_STATUS = "check_status"
    CANCEL_TASK = "cancel_task"
    PAUSE_TASK = "pause_task"
    UPLOAD_FILE = "upload_file"
    RESEARCH = "research"
    GENERAL_CONVERSATION = "general_conversation"
    NOISE = "noise"


# ---------------------------------------------------------------------------
# Internal Message (output of Ingress Parser)
# ---------------------------------------------------------------------------

class InternalMessage(BaseModel):
    id: str
    chat_id: str
    chat_type: ChatType
    sender_id: str
    sender_name: str = ""
    timestamp: datetime
    type: MessageType = MessageType.TEXT
    content: str = ""
    content_hash: str = ""
    media_id: str | None = None
    media_filename: str | None = None
    media_mime: str | None = None
    is_forwarded: bool = False
    is_bot_mention: bool = False
    bot_command: str | None = None
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Intent Classification (output of Router Agent)
# ---------------------------------------------------------------------------

class ClassifiedIntent(BaseModel):
    intent: IntentType
    confidence: float = 1.0
    priority: TaskPriority = TaskPriority.P1
    assignee: str | None = None
    deadline: str | None = None
    entities: list[str] = Field(default_factory=list)
    raw_command: str = ""


# ---------------------------------------------------------------------------
# Tool Definitions (MCP-compatible)
# ---------------------------------------------------------------------------

class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """Matches OpenAI function calling schema for direct LLM integration."""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    category: str = "general"


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    data: Any = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Agent Messages
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    db_size_mb: float
    disk_free_mb: float
    tasks_pending: int
    last_message_at: str | None
    last_backup_at: str | None


class TaskOut(BaseModel):
    id: str
    assigner_name: str | None = None
    assignee_name: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    deadline: str | None = None
    created_at: str
    updated_at: str


class WebhookAck(BaseModel):
    status: str = "ok"
    message_id: str | None = None
