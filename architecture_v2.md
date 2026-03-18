# SYSTEM ARCHITECTURE SPECIFICATION V2
## NSI WhatsApp Business Automation Platform

| Field | Value |
|-------|-------|
| **Version** | 2.0 (Final — locked for V1 implementation) |
| **Date** | March 17, 2026 |
| **Target Environment** | DigitalOcean VPS (1-2GB RAM, 1 vCPU, 25GB SSD) |
| **Primary Language** | Python 3.12+ |
| **Framework** | FastAPI (async) |
| **Database** | SQLite 3 (WAL mode) |
| **LLM** | KIMI K2 via NVIDIA API (128K context, 40 RPM) |
| **File Storage** | Google Drive (Service Account) |
| **Tunnel** | OpenClaw (WhatsApp Web via Baileys) |
| **Domain** | `bot.stelastra.com` |

---

## 1. SYSTEM TOPOLOGY

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DIGITALOCEAN VPS                             │
│                   (1-2GB RAM, 1 vCPU, 25GB SSD)                     │
│                                                                     │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐   │
│  │  Caddy    │───►│          FastAPI Application                 │   │
│  │  Reverse  │    │                                              │   │
│  │  Proxy    │    │  ┌─────────────┐  ┌──────────────────────┐  │   │
│  │  (HTTPS)  │    │  │  Webhook    │  │  Dashboard            │  │   │
│  │           │    │  │  Handler    │  │  (Static React/Jinja) │  │   │
│  └──────────┘    │  │  /webhook   │  │  /dashboard/*         │  │   │
│       ▲          │  └──────┬──────┘  └──────────────────────┘  │   │
│       │          │         │                                    │   │
│   Let's Encrypt  │         ▼                                    │   │
│   Auto-SSL       │  ┌──────────────┐                            │   │
│                  │  │ Async Queue  │ (asyncio.Queue)            │   │
│                  │  └──────┬───────┘                            │   │
│                  │         │                                    │   │
│                  │         ▼                                    │   │
│                  │  ┌──────────────────────────────────────┐   │   │
│                  │  │        MESSAGE PROCESSOR              │   │   │
│                  │  │                                       │   │   │
│                  │  │  ┌───────────┐  ┌─────────────────┐  │   │   │
│                  │  │  │ Ingress   │  │ Intent Router   │  │   │   │
│                  │  │  │ Parser    │──►│ (LLM + Rules)   │  │   │   │
│                  │  │  │ + PII     │  │                 │  │   │   │
│                  │  │  │ Redactor  │  └────────┬────────┘  │   │   │
│                  │  │  └───────────┘           │           │   │   │
│                  │  │                          ▼           │   │   │
│                  │  │  ┌──────┬───────┬───────┬────────┐  │   │   │
│                  │  │  │Task  │Doc    │File   │Query   │  │   │   │
│                  │  │  │Engine│Gen    │Sync   │Handler │  │   │   │
│                  │  │  └──┬───┴───┬───┴───┬───┴────┬───┘  │   │   │
│                  │  │     │       │       │        │       │   │   │
│                  │  └─────┼───────┼───────┼────────┼───────┘   │   │
│                  │        │       │       │        │            │   │
│                  │        ▼       ▼       ▼        ▼            │   │
│                  │  ┌──────────────────────────────────────┐   │   │
│                  │  │            SHARED SERVICES            │   │   │
│                  │  │                                       │   │   │
│                  │  │  ┌──────────┐  ┌──────────────────┐  │   │   │
│                  │  │  │ LLM      │  │ SQLite Database   │  │   │   │
│                  │  │  │ Gateway  │  │ (WAL mode)        │  │   │   │
│                  │  │  │ (KIMI→   │  │                   │  │   │   │
│                  │  │  │  GPT→    │  │ ┌───────────────┐ │  │   │   │
│                  │  │  │  Claude) │  │ │ messages      │ │  │   │   │
│                  │  │  └──────────┘  │ │ entities      │ │  │   │   │
│                  │  │                │ │ relationships │ │  │   │   │
│                  │  │  ┌──────────┐  │ │ tasks         │ │  │   │   │
│                  │  │  │ Google   │  │ │ documents     │ │  │   │   │
│                  │  │  │ Drive    │  │ │ buffers       │ │  │   │   │
│                  │  │  │ Client   │  │ │ token_usage   │ │  │   │   │
│                  │  │  └──────────┘  │ └───────────────┘ │  │   │   │
│                  │  │                └──────────────────┘  │   │   │
│                  │  │  ┌──────────┐  ┌──────────────────┐  │   │   │
│                  │  │  │ Outbound │  │ Email Client     │  │   │   │
│                  │  │  │ WhatsApp │  │ (MSAL OAuth2)    │  │   │   │
│                  │  │  │ Gateway  │  │ info@stelastra   │  │   │   │
│                  │  │  └──────────┘  └──────────────────┘  │   │   │
│                  │  └──────────────────────────────────────┘   │   │
│                  │                                              │   │
│                  │  ┌──────────────────────────────────────┐   │   │
│                  │  │        BACKGROUND WORKERS             │   │   │
│                  │  │                                       │   │   │
│                  │  │  ┌──────────┐  ┌──────────────────┐  │   │   │
│                  │  │  │ Chaser   │  │ Context          │  │   │   │
│                  │  │  │ Cron     │  │ Condenser        │  │   │   │
│                  │  │  │ (1h loop)│  │ (30min timeout)  │  │   │   │
│                  │  │  └──────────┘  └──────────────────┘  │   │   │
│                  │  │                                       │   │   │
│                  │  │  ┌──────────┐  ┌──────────────────┐  │   │   │
│                  │  │  │ DB       │  │ EOD Report       │  │   │   │
│                  │  │  │ Backup   │  │ Generator        │  │   │   │
│                  │  │  │ (1h)     │  │ (6PM IST daily)  │  │   │   │
│                  │  │  └──────────┘  └──────────────────┘  │   │   │
│                  │  │                                       │   │   │
│                  │  │  ┌──────────┐  ┌──────────────────┐  │   │   │
│                  │  │  │ Log      │  │ Heartbeat        │  │   │   │
│                  │  │  │ Rotator  │  │ (1h WA ping)     │  │   │   │
│                  │  │  │ (daily)  │  │                   │  │   │   │
│                  │  │  └──────────┘  └──────────────────┘  │   │   │
│                  │  └──────────────────────────────────────┘   │   │
│                  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

         ▲                    ▲                    ▲
         │                    │                    │
    OpenClaw              NVIDIA API          Google Drive
    WhatsApp              KIMI K2 / GPT       Service Acct
    Gateway               / Claude Haiku      (50GB)
    (WebSocket)           (HTTPS)             (HTTPS)
```

---

## 2. TECH STACK (FINAL DECISION MATRIX)

| Component | Choice | Justification |
|-----------|--------|---------------|
| **Language** | Python 3.12+ | Async support, rich LLM ecosystem, FastAPI, APScheduler |
| **Web Framework** | FastAPI (uvicorn) | Async, lightweight, built-in OpenAPI docs, serves static files |
| **Database** | SQLite 3 (WAL mode) + `aiosqlite` | Zero RAM when idle, WAL for concurrent reads, single-writer queue |
| **Task Scheduler** | APScheduler (AsyncIOScheduler) | Runs inside main process, no extra daemon, cron-like triggers |
| **LLM Client** | `openai` Python SDK (OpenAI-compatible) | NVIDIA API is OpenAI-compatible; same client for GPT/Claude fallbacks |
| **File Storage** | Google Drive API v3 (`google-api-python-client`) | Service Account auth, resumable uploads, zero local storage cost |
| **Email** | `msal` + `smtplib` | OAuth2 token acquisition for Microsoft 365, standard SMTP send |
| **WhatsApp Outbound** | OpenClaw Gateway WebSocket (`websockets`) | Direct integration with running OpenClaw instance |
| **Reverse Proxy** | Caddy v2 | Automatic Let's Encrypt HTTPS, zero config, ~50MB RAM |
| **Dashboard Frontend** | Preact + HTM (no build step) or Jinja2 templates | Minimal JS, mobile-first, served from FastAPI static dir |
| **Containerization** | Docker + docker-compose | Single-command deployment, volume mounts for SQLite + config |
| **PII Detection** | Regex patterns + `presidio-analyzer` (Microsoft, lightweight) | Detect OTPs, card numbers, bank refs before storage |
| **Document Generation** | `python-docx` + templates | Programmatic DOCX creation from template files |
| **PDF Conversion** | `libreoffice --headless` (CLI) or `weasyprint` | Convert DOCX → PDF for WhatsApp delivery |

### RAM Budget (Target: < 500MB total)

| Component | Estimated RAM |
|-----------|---------------|
| Caddy reverse proxy | ~50 MB |
| FastAPI + uvicorn (1 worker) | ~80 MB |
| SQLite (WAL, indexed) | ~20 MB |
| APScheduler (6 jobs) | ~10 MB |
| Python application code + deps | ~120 MB |
| Temporary file processing buffer | ~50 MB |
| **Total** | **~330 MB** |
| **Headroom for spikes** | ~170-670 MB |

---

## 3. COMPONENT ARCHITECTURE

### 3.1 Webhook Handler (`/api/webhook`)

**Responsibility:** Accept OpenClaw webhook POST, validate, deduplicate, enqueue, ACK.

```
Request Flow:
POST /api/webhook
  │
  ├─ 1. Validate payload structure (WhatsApp Cloud API envelope)
  ├─ 2. Extract messageId from payload
  ├─ 3. Check idempotency: SELECT FROM processed_messages WHERE message_id = ?
  │     ├─ If exists → return 200 OK (already processed)
  │     └─ If new → INSERT into processed_messages (TTL: 1 hour cleanup)
  ├─ 4. Enqueue raw payload into asyncio.Queue
  └─ 5. Return 200 OK (< 500ms total)
```

**Critical constraint:** No LLM calls, no Drive uploads, no heavy processing in this handler. Must respond within 500ms to avoid OpenClaw retry (10s timeout).

### 3.2 Ingress Parser

**Responsibility:** Transform raw webhook payload into normalized internal message format, redact PII, store in SQLite.

```python
# Internal message format after parsing
InternalMessage = {
    "id": str,                  # messageId from WhatsApp
    "chat_id": str,             # group JID or personal JID
    "chat_type": "group" | "dm",
    "sender_id": str,           # phone number (E.164)
    "sender_name": str,         # resolved from hardcoded map or profile
    "timestamp": datetime,
    "type": "text" | "image" | "document" | "audio" | "video" | "location" | "contact" | "system",
    "content": str,             # text body (PII-redacted)
    "content_raw_hash": str,    # SHA-256 of original content (for audit without storing PII)
    "media_id": str | None,     # WhatsApp media ID for file download
    "media_filename": str | None,
    "media_mime": str | None,
    "is_forwarded": bool,
    "is_bot_mention": bool,     # contains @nsi
    "bot_command": str | None,  # extracted command after @nsi
    "language": "en" | "hi" | "other",
    "metadata": dict            # raw OpenClaw context fields
}
```

**PII Redaction Pipeline:**
1. OTP detection: `/\b\d{4,8}\b/` near keywords "OTP", "One Time Password", "verification code"
2. Card number detection: `/\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/` or "ending XXXX" patterns
3. Bank transaction references: patterns containing "txn", "Reference #", bank names + amounts
4. Redaction format: replace with `[REDACTED:OTP]`, `[REDACTED:CARD]`, `[REDACTED:BANK_REF]`

### 3.3 Intent Router

**Responsibility:** Classify messages and route to appropriate handler.

**Two-stage routing:**

**Stage 1 — Rule-based (zero LLM cost):**
```
IF message.is_bot_mention:
    command = message.bot_command.lower()
    IF command starts with "generate" | "make" | "create" | "draft":
        → DocumentGenerator
    IF command starts with "assign" | "task" | "remind":
        → TaskEngine
    IF command starts with "status" | "check" | "what's pending":
        → QueryHandler (task status)
    IF command starts with "cancel task" | "pause task":
        → TaskEngine (control)
    IF command starts with "compare" | "check prices":
        → ContextBuffer (open collection mode)
    IF command starts with "find" | "search" | "fetch" | "get":
        → QueryHandler (document/data search)
    ELSE:
        → Stage 2 (LLM classification)
ELSE (passive mode):
    → PassiveIndexer (store message, extract entities)
```

**Stage 2 — LLM classification (8K token budget):**
```
System prompt: "Classify this WhatsApp message into one of: 
  generate_document, assign_task, query_data, compare_files, 
  check_status, cancel_task, general_conversation, spam/noise.
  Also extract: assignee, deadline, priority (P0/P1/P2), relevant entities.
  Respond in JSON only."

Input: last 5 messages for context + current message
```

### 3.4 Context Buffer Manager

**Responsibility:** Manage multi-message collection sessions.

**State machine per buffer:**
```
IDLE → COLLECTING → PROCESSING → COMPLETE
         │    ▲
         │    │ (new related message after timeout)
         ▼    │
       TIMED_OUT ─── (intent re-detected) ───► COLLECTING
```

**Storage:** SQLite `context_buffers` table.

```sql
CREATE TABLE context_buffers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    intent_hash TEXT NOT NULL,
    status TEXT DEFAULT 'collecting',  -- collecting, timed_out, processing, complete
    messages TEXT DEFAULT '[]',        -- JSON array of message IDs
    media_ids TEXT DEFAULT '[]',       -- JSON array of media references
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    timeout_minutes INTEGER DEFAULT 10,
    UNIQUE(user_id, chat_id, intent_hash)
);
```

**Timeout logic:** APScheduler job checks every 60 seconds for buffers where `last_activity_at + timeout_minutes < NOW()`. On timeout, auto-process or transition to `timed_out`. If a new message arrives matching the same `intent_hash`, re-open the buffer.

### 3.5 LLM Gateway

**Responsibility:** Manage all LLM API calls with rate limiting, fallback, and token tracking.

```
┌──────────────────────────────────────────────┐
│              LLM GATEWAY                     │
│                                              │
│  ┌────────────┐                              │
│  │ Token      │  40 RPM limit for KIMI K2    │
│  │ Bucket     │  Refills 1 token / 1.5s      │
│  │ Rate       │                              │
│  │ Limiter    │                              │
│  └─────┬──────┘                              │
│        │                                     │
│        ▼                                     │
│  ┌────────────────────────────┐              │
│  │ Provider Chain             │              │
│  │                            │              │
│  │  1. KIMI K2 (NVIDIA API)  │ ◄─ Primary   │
│  │  2. GPT-4o-mini (OpenAI)  │ ◄─ Fallback  │
│  │  3. Claude Haiku (Anthro) │ ◄─ Emergency  │
│  │                            │              │
│  │  On 429/5xx/timeout:      │              │
│  │    → next provider        │              │
│  │    → 3 retries per        │              │
│  │    → exponential backoff  │              │
│  └─────┬──────────────────────┘              │
│        │                                     │
│        ▼                                     │
│  ┌────────────┐                              │
│  │ Token      │  Log: provider, model,       │
│  │ Usage      │  prompt_tokens, completion_   │
│  │ Tracker    │  tokens, cost_estimate,       │
│  │            │  latency_ms, request_type     │
│  └────────────┘                              │
└──────────────────────────────────────────────┘
```

**Context window budgets:**

| Request Type | Max Tokens | Use Case |
|-------------|-----------|----------|
| Intent classification | 8,000 | Route messages to handlers |
| Task extraction | 16,000 | Parse task details from conversation |
| Document generation | 32,000 | Generate PI/Quotation with full context |
| Monthly summary / EOD | 64,000 | Aggregate and summarize large volumes |

### 3.6 Task Engine & Chaser

**Responsibility:** Create tasks, track state, execute escalation protocol.

**Task lifecycle:**
```
DETECTED → PENDING → NUDGED_1 → NUDGED_2 → ESCALATED → [COMPLETED | CANCELLED | PAUSED]
                                                              ▲
                                                              │
                                              (user says "done"/"ok")
```

**Chaser cron job (APScheduler, runs every 60 minutes):**

```python
# Pseudocode for Chaser loop
async def chaser_tick():
    now = datetime.now(IST)
    
    # Respect quiet window: 2 AM - 8 AM IST
    if 2 <= now.hour < 8:
        return
    
    overdue_tasks = await db.execute("""
        SELECT * FROM tasks 
        WHERE status IN ('pending', 'nudged_1', 'nudged_2')
        AND (last_nudged_at IS NULL OR last_nudged_at < datetime('now', '-55 minutes'))
        ORDER BY priority ASC, created_at ASC
    """)
    
    for task in overdue_tasks:
        hours_elapsed = (now - task.created_at).total_seconds() / 3600
        thresholds = ESCALATION_MATRIX[task.priority]
        
        if hours_elapsed >= thresholds.email_hours and task.status != 'escalated':
            await send_escalation_email(task)
            await db.update_task(task.id, status='escalated', last_nudged_at=now)
        elif hours_elapsed >= thresholds.firm_chase_hours and task.status == 'nudged_1':
            await send_whatsapp_nudge(task, template='firm')
            await db.update_task(task.id, status='nudged_2', last_nudged_at=now)
        elif hours_elapsed >= thresholds.nudge_hours and task.status == 'pending':
            await send_whatsapp_nudge(task, template='gentle')
            await db.update_task(task.id, status='nudged_1', last_nudged_at=now)
```

**Nudge templates (hardcoded, variable injection):**
```
gentle: "Hi {assignee}, friendly reminder: '{task_description}' — assigned {hours}h ago. Reply 'done' when complete."
firm:   "Hey {assignee}, '{task_description}' is now overdue ({hours}h). Any blockers? Reply 'done' or let me know."
email:  "Subject: [OVERDUE] Task: {task_description}\nAssigned to: {assignee}\nOverdue by: {hours}h\nOriginal assigner: {assigner}\nPlease complete or respond with an update."
```

### 3.7 Document Generation Engine

**Responsibility:** Generate business documents from templates with LLM-extracted variables.

```
Flow:
1. User: "@nsi generate proforma invoice for 3M liter tank"
2. Bot: "Working on it... Gathering data."
3. System:
   a. Query SQLite for relevant entities (vendor, pricing, specs)
   b. Send to LLM (32K budget): "Extract line items, quantities, 
      pricing, terms from this context. Return JSON only."
   c. Validate: ALL prices must exist in SQLite. If LLM invents 
      a price not in DB → flag for human review.
   d. Load DOCX template from templates/{brand}/{doc_type}.docx
   e. Inject variables using python-docx
   f. Convert to PDF (libreoffice --headless)
   g. Self-evaluate: check required fields, math validation
   h. If confidence >= 80%: send PDF to chat
      If confidence < 80%: send with warning
4. User: "Approved" → upload to Drive, log metadata
         "Change the payment terms" → LLM re-extracts, regenerate
```

**Template directory structure:**
```
templates/
├── pacific_unity/
│   ├── proforma_invoice.docx
│   ├── commercial_quotation.docx
│   ├── packing_list.docx
│   └── letterhead.docx
├── stel_astra/
│   ├── proforma_invoice.docx
│   └── ...
├── nsi_projects/
│   └── ...
└── shared/
    ├── logo_pacific_unity.png
    ├── logo_stel_astra.png
    └── brand_config.json   # colors, fonts, addresses per brand
```

### 3.8 Google Drive Sync Service

**Responsibility:** Upload files, manage folder structure, backup database.

**Authentication:** Google Service Account. The Service Account email is added as an Editor to a shared folder on Shreyas's personal Drive.

**Folder hierarchy (project-based, per user's preference):**
```
PacificUnity_Bot/
├── Projects/
│   ├── 3M_Liter_Tank/
│   │   ├── Quotes/
│   │   ├── POs/
│   │   ├── Technical_Drawings/
│   │   └── Generated_Documents/
│   ├── Bottle_Filling_Line/
│   ├── Electrical_Installation/
│   └── _Unsorted/           ← files that can't be auto-categorized
├── General/
│   ├── Payment_Records/
│   ├── Company_Documents/
│   └── Miscellaneous/
├── Generated_Documents/      ← all bot-generated docs (cross-project)
│   ├── Proforma_Invoices/
│   ├── Commercial_Quotations/
│   ├── Packing_Lists/
│   └── Letterhead_Documents/
├── Chat_Backups/
│   └── Daily_Summaries/
└── System/
    ├── DB_Backups/
    └── Logs/
```

**Upload pipeline:**
```
1. Receive media_id from webhook
2. Download file from WhatsApp Cloud API → /tmp/drive_sync/{uuid}_{filename}
3. Compute SHA-256 hash
4. Check SQLite: SELECT FROM documents WHERE file_hash = ?
   ├─ If exists: store new version, flag as duplicate_of: {original_id}
   └─ If new: proceed
5. LLM classification (8K budget): "Which project does this file belong to? 
   Given filename '{name}' sent by '{sender}' in context '{last 3 messages}'.
   Return: project_name, subfolder, description."
6. Upload to Google Drive (resumable upload for files > 5MB)
   ├─ Retry 1 (400ms delay)
   ├─ Retry 2 (1.6s delay)
   ├─ Retry 3 (6.4s delay)
   └─ On final failure: alert Shreyas on WhatsApp, queue for next hourly cron
7. Store Drive link + metadata in SQLite documents table
8. Delete local /tmp/ file ONLY after upload confirmed (Drive file ID returned)
```

### 3.9 Email Service (Outlook MSAL)

**Responsibility:** Send escalation emails via `info@stelastra.com`.

**Authentication flow:**
```
1. Register Azure AD app (one-time setup)
   - Application (client) ID
   - Client secret or certificate
   - Grant: Mail.Send permission (application scope)
2. At runtime: MSAL ConfidentialClientApplication acquires token
3. Token cached in memory, auto-refreshes on expiry (typically 1 hour)
4. Send via Microsoft Graph API (POST /users/{email}/sendMail)
   OR via SMTP with OAuth2 bearer token (smtp.office365.com:587)
```

**CC rules (hardcoded in config):**
```json
{
  "always_cc": ["shreyas@stelastra.com"],
  "cc_on_p0": ["dad_africa_email@domain.com"],
  "from": "info@stelastra.com",
  "format": "plain_text"
}
```

### 3.10 WhatsApp Outbound Gateway

**Responsibility:** Send messages and media back to WhatsApp via OpenClaw.

**Integration:** Connect to OpenClaw's Gateway WebSocket. Messages are sent as JSON frames.

```python
# Outbound message format
{
    "action": "send",
    "channel": "whatsapp",
    "to": "<jid>",          # personal JID or group JID
    "type": "text" | "document" | "image",
    "content": "message text",
    "media_path": "/tmp/generated/invoice.pdf",  # for document type
    "media_filename": "Proforma_Invoice_001.pdf"
}
```

**Rate limiting:** Respect WhatsApp's tiered limits. Start at Tier 1 (80 messages/24h per unique recipient). Implement a send queue with 2-second spacing between messages to the same recipient.

### 3.11 Dashboard (FastAPI-served)

**Stack:** Preact + HTM (no build step, served as static JS from FastAPI).

**Routes:**
```
/dashboard/login          → Username + password form
/dashboard/               → Task list (default view)
/dashboard/tasks          → Full task management
/dashboard/chat           → 1-on-1 bot chat interface
/dashboard/search         → Document/file search
/dashboard/analytics      → Task analytics and metrics
/dashboard/upload         → File upload portal
/dashboard/buffers        → Active context buffer management
```

**Authentication:** Simple session-based auth.
```python
# config/users.json (hardcoded, loaded at startup)
{
  "users": [
    {"username": "shreyas", "password_hash": "bcrypt...", "role": "admin", "whatsapp_id": "+971..."},
    {"username": "govind", "password_hash": "bcrypt...", "role": "employee", "whatsapp_id": "+91..."},
    {"username": "shibu", "password_hash": "bcrypt...", "role": "employee", "whatsapp_id": "+91..."}
  ]
}
```

**API endpoints (FastAPI REST, used by dashboard frontend):**
```
GET    /api/tasks                    → List tasks (filters: status, assignee, priority)
PATCH  /api/tasks/{id}               → Update task (status, priority, assignee)
GET    /api/documents                → Search documents (query, date range, vendor)
POST   /api/upload                   → Upload file to Drive
GET    /api/analytics/summary        → Task metrics, employee performance
GET    /api/buffers                  → List active context buffers
POST   /api/buffers/{id}/trigger     → Manually trigger buffer processing
DELETE /api/buffers/{id}             → Close/cancel buffer
POST   /api/chat                    → Send message to bot (dashboard chat)
GET    /api/chat/history            → Get chat history for current user
GET    /api/health                  → Health check endpoint
```

---

## 4. DATA MODEL (SQLite Schema)

```sql
-- Enable WAL mode (set once at connection time)
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;

-- Schema version tracking for auto-migration
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Idempotency: track processed webhook message IDs
CREATE TABLE processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- Cleanup: DELETE FROM processed_messages WHERE processed_at < datetime('now', '-1 hour')

-- Core message store (PII-redacted content)
CREATE TABLE messages (
    id TEXT PRIMARY KEY,                    -- WhatsApp messageId
    chat_id TEXT NOT NULL,                  -- group JID or personal JID
    chat_type TEXT NOT NULL,                -- 'group' or 'dm'
    sender_id TEXT NOT NULL,                -- phone number E.164
    sender_name TEXT,                       -- resolved name
    timestamp DATETIME NOT NULL,
    type TEXT NOT NULL,                     -- text, image, document, audio, video, system
    content TEXT,                           -- PII-redacted text
    content_hash TEXT,                      -- SHA-256 of original (for dedup without PII)
    media_id TEXT,                          -- WhatsApp media ID
    media_filename TEXT,
    media_mime TEXT,
    is_forwarded BOOLEAN DEFAULT 0,
    is_bot_mention BOOLEAN DEFAULT 0,
    bot_command TEXT,
    language TEXT DEFAULT 'en',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_messages_chat_ts ON messages(chat_id, timestamp);
CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_messages_bot ON messages(is_bot_mention) WHERE is_bot_mention = 1;

-- Employee/contact registry
CREATE TABLE employees (
    id TEXT PRIMARY KEY,
    whatsapp_id TEXT UNIQUE NOT NULL,       -- phone number E.164
    name TEXT NOT NULL,
    role TEXT NOT NULL,                     -- admin, employee, external
    email TEXT,
    timezone TEXT DEFAULT 'Asia/Kolkata',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Entity graph: vendors, companies, materials, equipment
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                     -- vendor, company, material, equipment, project
    name TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',             -- JSON: address, contact, specs, etc.
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities(name);

-- Relationships between entities (graph emulation)
CREATE TABLE relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES entities(id),
    target_id TEXT NOT NULL REFERENCES entities(id),
    relation_type TEXT NOT NULL,            -- quoted_for, supplied_to, part_of, priced_at, etc.
    metadata TEXT DEFAULT '{}',             -- JSON: price, date, conditions
    source_message_id TEXT REFERENCES messages(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relation_type)
);
CREATE INDEX idx_rel_source ON relationships(source_id);
CREATE INDEX idx_rel_target ON relationships(target_id);
CREATE INDEX idx_rel_type ON relationships(relation_type);

-- Task management
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    assigner_id TEXT REFERENCES employees(id),
    assignee_id TEXT NOT NULL REFERENCES employees(id),
    description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'P1',    -- P0, P1, P2
    status TEXT NOT NULL DEFAULT 'pending', -- pending, nudged_1, nudged_2, escalated, completed, cancelled, paused
    source_chat_id TEXT,
    source_message_id TEXT REFERENCES messages(id),
    deadline DATETIME,
    completed_at DATETIME,
    last_nudged_at DATETIME,
    nudge_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_overdue ON tasks(status, last_nudged_at);

-- Document registry (files uploaded to Google Drive)
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    mime_type TEXT,
    file_hash TEXT,                          -- SHA-256 for dedup
    file_size_bytes INTEGER,
    drive_url TEXT,                          -- Google Drive webViewLink
    drive_file_id TEXT,                      -- Google Drive file ID
    folder_path TEXT,                        -- Drive folder path
    source_chat_id TEXT,
    source_message_id TEXT REFERENCES messages(id),
    uploaded_by TEXT REFERENCES employees(id),
    project TEXT,                            -- auto-categorized project
    doc_type TEXT,                           -- quote, po, technical_drawing, invoice, etc.
    description TEXT,
    extracted_text TEXT,                     -- OCR/PDF text extraction
    duplicate_of TEXT REFERENCES documents(id),
    status TEXT DEFAULT 'pending_upload',    -- pending_upload, uploaded, upload_failed, queued_retry
    local_path TEXT,                         -- temp local path (until uploaded)
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_docs_hash ON documents(file_hash);
CREATE INDEX idx_docs_project ON documents(project);
CREATE INDEX idx_docs_status ON documents(status);

-- Context buffers
CREATE TABLE context_buffers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    intent_hash TEXT NOT NULL,
    status TEXT DEFAULT 'collecting',
    message_ids TEXT DEFAULT '[]',
    media_ids TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    timeout_minutes INTEGER DEFAULT 10,
    UNIQUE(user_id, chat_id, intent_hash)
);

-- Generated documents (bot-created)
CREATE TABLE generated_documents (
    id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,                 -- proforma_invoice, commercial_quotation, packing_list, letterhead
    brand TEXT NOT NULL,                    -- pacific_unity, stel_astra, nsi_projects, etc.
    status TEXT DEFAULT 'draft',            -- draft, approved, rejected, superseded
    template_used TEXT,
    variables_json TEXT,                    -- JSON: all injected variables
    self_eval_score REAL,                   -- 0.0 - 1.0 confidence score
    self_eval_issues TEXT,                  -- JSON: list of flagged issues
    drive_url TEXT,
    drive_file_id TEXT,
    requested_by TEXT REFERENCES employees(id),
    approved_by TEXT REFERENCES employees(id),
    source_chat_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME
);

-- Token usage tracking
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,                 -- nvidia, openai, anthropic
    model TEXT NOT NULL,                    -- kimi-k2-instruct, gpt-4o-mini, claude-haiku
    request_type TEXT NOT NULL,             -- intent_classification, task_extraction, doc_generation, etc.
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    cost_estimate_usd REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_token_provider ON token_usage(provider, created_at);

-- Conversation summaries (context condenser output)
CREATE TABLE conversation_summaries (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    summary TEXT NOT NULL,
    extracted_facts TEXT DEFAULT '[]',      -- JSON: prices, decisions, assignments
    message_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_summaries_chat ON conversation_summaries(chat_id, period_end);

-- Cross-chat privacy permissions
CREATE TABLE privacy_permissions (
    id TEXT PRIMARY KEY,
    data_owner_id TEXT NOT NULL REFERENCES employees(id),
    data_type TEXT NOT NULL,                -- entity_id, document_id, etc.
    data_reference TEXT NOT NULL,
    requested_by_chat_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',          -- pending, approved, denied
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

-- Dashboard sessions
CREATE TABLE dashboard_sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES employees(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);
```

---

## 5. SEQUENCE DIAGRAMS

### 5.1 Incoming Message (Happy Path)

```
WhatsApp User    OpenClaw    FastAPI     Queue    Parser    Router    Handler    SQLite    Drive
     │               │          │          │        │         │          │         │        │
     │──message──►   │          │          │        │         │          │         │        │
     │               │──POST──► │          │        │         │          │         │        │
     │               │          │──dedup──►│        │         │          │         │        │
     │               │          │◄─new─────│        │         │          │         │        │
     │               │          │──enqueue─►        │         │          │         │        │
     │               │  ◄──200 OK──│       │        │         │          │         │        │
     │               │          │          │──pop──►│         │          │         │        │
     │               │          │          │        │──parse──►          │         │        │
     │               │          │          │        │──redact PII──►     │         │        │
     │               │          │          │        │──store──────────────────────►│        │
     │               │          │          │        │         │          │         │        │
     │               │          │          │        │──route──►          │         │        │
     │               │          │          │        │         │──execute─►         │        │
     │               │          │          │        │         │          │──query──►│        │
     │               │          │          │        │         │          │──upload──────────►│
     │               │          │          │        │         │          │         │        │
     │  ◄──────────────────────────response─────────────────────        │         │        │
```

### 5.2 Document Generation Flow

```
User         Bot          LLM Gateway     SQLite     DocEngine    Drive     Chat
  │            │               │             │           │          │         │
  │─"@nsi make PI"──►         │             │           │          │         │
  │            │               │             │           │          │         │
  │  ◄─"Working on it..."─    │             │           │          │         │
  │            │               │             │           │          │         │
  │            │──extract vars─►             │           │          │         │
  │            │               │──query───────►          │          │         │
  │            │               │◄─prices,terms─          │          │         │
  │            │◄──variables JSON──           │           │          │         │
  │            │               │             │           │          │         │
  │            │──validate prices vs DB──────►           │          │         │
  │            │◄──all prices confirmed──────            │          │         │
  │            │               │             │           │          │         │
  │            │──generate DOCX──────────────────────────►          │         │
  │            │               │             │           │──to PDF──►         │
  │            │◄──────────────────────────────PDF ready──          │         │
  │            │               │             │           │          │         │
  │            │──self-evaluate (score)──►    │           │          │         │
  │            │               │             │           │          │         │
  │  ◄─draft PDF + "Approve or suggest changes"─────────────────────────────►│
  │            │               │             │           │          │         │
  │─"Approved"─►              │             │           │          │         │
  │            │──upload final──────────────────────────────────────►         │
  │            │◄──Drive URL───────────────────────────────────────          │
  │            │──log metadata───────────────►           │          │         │
  │  ◄─"Done! Saved to Drive: {url}"─────────────────────────────────────────►
```

---

## 6. SECURITY ARCHITECTURE

### 6.1 Network Security

```
Internet ──► Caddy (port 443, HTTPS only) ──► FastAPI (127.0.0.1:8000)
                                                      │
                                              UFW: only 80/443 open
                                              SSH: key-only, non-standard port
                                              fail2ban: active
```

### 6.2 Secret Management

All secrets stored as environment variables in `/opt/nsi-bot/.env` (not in code, not in git):

```env
# LLM Providers
NVIDIA_API_KEY=nvapi-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Google Drive
GOOGLE_SERVICE_ACCOUNT_JSON=/opt/nsi-bot/credentials/gdrive-sa.json

# Microsoft 365 (Email)
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_TENANT_ID=...
EMAIL_FROM=info@stelastra.com

# OpenClaw
OPENCLAW_WS_URL=ws://localhost:3000/gateway
OPENCLAW_API_KEY=...

# Dashboard
DASHBOARD_SECRET_KEY=...  # for session signing

# Database
DB_PATH=/opt/nsi-bot/data/nsi.db
```

### 6.3 Webhook Verification

Validate incoming webhooks by checking the source IP matches OpenClaw's local address (since OpenClaw runs on the same VPS) or by verifying a shared secret header.

---

## 7. DEPLOYMENT ARCHITECTURE

### 7.1 Docker Compose

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    container_name: nsi-bot
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/opt/nsi-bot/data          # SQLite DB
      - ./templates:/opt/nsi-bot/templates # DOCX templates
      - ./credentials:/opt/nsi-bot/credentials # Service account JSON
      - /tmp/drive_sync:/tmp/drive_sync   # Temp file staging
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  caddy:
    image: caddy:2-alpine
    container_name: nsi-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

### 7.2 Caddyfile

```
bot.stelastra.com {
    reverse_proxy app:8000
    encode gzip
    header {
        X-Robots-Tag "noindex, nofollow"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }
}
```

### 7.3 Deployment Procedure

```bash
# Manual deployment (at 4 AM IST during quiet window)
ssh nsi-vps
cd /opt/nsi-bot
git pull origin main
docker-compose down
docker-compose up --build -d
docker-compose logs -f --tail=50  # verify startup
```

### 7.4 DNS Setup Guide (for bot.stelastra.com)

1. Log into your domain registrar for `stelastra.com`
2. Go to DNS management
3. Add an **A record**:
   - **Name:** `bot`
   - **Type:** A
   - **Value:** `<your DigitalOcean VPS IP address>`
   - **TTL:** 300 (5 minutes)
4. Wait 5-30 minutes for DNS propagation
5. Verify: `nslookup bot.stelastra.com` should return your VPS IP
6. Caddy auto-provisions the HTTPS certificate on first request

---

## 8. MONITORING & OPERATIONS

### 8.1 Health Check Endpoint

```
GET /api/health → 200 OK
{
    "status": "healthy",
    "uptime_seconds": 86400,
    "db_size_mb": 12.5,
    "disk_free_mb": 18000,
    "tasks_pending": 7,
    "last_message_at": "2026-03-17T14:30:00Z",
    "last_backup_at": "2026-03-17T14:00:00Z",
    "llm_credits_remaining": 4200
}
```

### 8.2 UptimeRobot

- Monitor: `https://bot.stelastra.com/api/health`
- Interval: 5 minutes
- Alert: Email + SMS to Shreyas on downtime

### 8.3 WhatsApp Heartbeat

APScheduler job every 1 hour: send message to a private "Bot Status" chat:
```
"[Heartbeat] NSI Bot alive. Uptime: 24h 15m. Tasks pending: 7. DB: 12.5MB. Disk free: 18GB."
```

If Shreyas stops receiving these, the bot is down.

### 8.4 Log Management

- **Format:** Structured JSON (one line per log entry)
- **Location:** `/opt/nsi-bot/data/logs/`
- **Rotation:** Daily, max 7 files, max 500MB total
- **Archival:** Before deletion, upload to `System/Logs/` on Google Drive
- **Levels:** INFO for normal ops, WARNING for retries, ERROR for failures, CRITICAL for data loss risks

### 8.5 Google Drive Service Account Setup Guide

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "NSI Bot")
3. Enable the **Google Drive API**
4. Go to **IAM & Admin** → **Service Accounts**
5. Create a Service Account (e.g., `nsi-bot@nsi-bot-project.iam.gserviceaccount.com`)
6. Generate a JSON key file → download as `gdrive-sa.json`
7. Place `gdrive-sa.json` in `/opt/nsi-bot/credentials/` on the VPS
8. In your **personal Google Drive**:
   a. Create a folder called `PacificUnity_Bot`
   b. Right-click → Share → Add the Service Account email as **Editor**
9. The bot can now read/write inside that shared folder

---

## 9. PROJECT DIRECTORY STRUCTURE

```
nsi-bot/
├── docker-compose.yml
├── Dockerfile
├── Caddyfile
├── .env.example
├── requirements.txt
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, lifespan, middleware
│   ├── config.py                  # Settings loaded from env vars
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhook.py             # POST /api/webhook
│   │   ├── tasks.py               # Task CRUD endpoints
│   │   ├── documents.py           # Document search endpoints
│   │   ├── analytics.py           # Analytics endpoints
│   │   ├── chat.py                # Dashboard chat endpoints
│   │   ├── upload.py              # File upload endpoint
│   │   ├── buffers.py             # Context buffer management
│   │   ├── health.py              # Health check
│   │   └── auth.py                # Dashboard authentication
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite connection, WAL, migrations
│   │   ├── queue.py               # Async message queue
│   │   ├── scheduler.py           # APScheduler setup (Chaser, backup, etc.)
│   │   └── migrations/            # Auto-run SQL migration scripts
│   │       ├── 001_initial.sql
│   │       └── ...
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingress.py             # Message parsing + PII redaction
│   │   ├── router.py              # Intent classification + routing
│   │   ├── llm_gateway.py         # LLM provider chain + rate limiter
│   │   ├── task_engine.py         # Task CRUD + state machine
│   │   ├── chaser.py              # Escalation cron logic
│   │   ├── doc_generator.py       # DOCX template injection + PDF conversion
│   │   ├── drive_sync.py          # Google Drive upload/backup
│   │   ├── email_service.py       # MSAL OAuth2 + send email
│   │   ├── whatsapp_outbound.py   # OpenClaw WebSocket outbound
│   │   ├── context_buffer.py      # Buffer manager state machine
│   │   ├── entity_extractor.py    # Extract vendors, prices, specs from messages
│   │   ├── eod_report.py          # Daily/weekly report generation
│   │   └── self_evaluator.py      # Document confidence scoring
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic models for all data types
│   │
│   └── static/                    # Dashboard frontend
│       ├── index.html
│       ├── app.js                 # Preact + HTM (no build step)
│       ├── style.css
│       └── assets/
│
├── templates/                     # DOCX templates (user-provided)
│   ├── pacific_unity/
│   ├── stel_astra/
│   └── shared/
│
├── credentials/                   # .gitignore'd
│   └── gdrive-sa.json
│
├── data/                          # .gitignore'd, Docker volume
│   ├── nsi.db
│   └── logs/
│
├── config/
│   └── users.json                 # Employee credentials for dashboard
│
└── tests/
    ├── test_ingress.py
    ├── test_router.py
    ├── test_chaser.py
    └── test_doc_generator.py
```

---

*This architecture is LOCKED for V1 implementation. Any structural changes require a versioned amendment.*
