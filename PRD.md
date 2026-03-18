# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## NSI WhatsApp Business Automation Platform

| Field | Value |
|-------|-------|
| **Product Name** | NSI Bot (configurable: `@nsi`) |
| **Version** | 1.0 (V1 Release) |
| **Date** | March 17, 2026 |
| **Status** | LOCKED — Approved for implementation |
| **Owner** | Shreyas Sunil |
| **Company** | North Star Impex Group (Pacific Unity MEA FZ-LLC) |

---

## 1. EXECUTIVE SUMMARY

NSI Bot is a WhatsApp-native business automation platform that turns chaotic multi-chat conversations into structured, actionable workflows. It sits behind an OpenClaw tunnel on a single WhatsApp number, monitors 4+ group/personal chats, and autonomously:

- Parses unstructured messages and file attachments (PDF, DOCX, XLSX, images)
- Assigns and tracks tasks with persistent, escalating follow-ups ("The Chaser")
- Generates branded business documents (Proforma Invoices, Commercial Quotations, Packing Lists)
- Organizes files into a structured Google Drive hierarchy
- Surfaces analytics and daily EOD reports
- Provides employees with a mobile-first web dashboard

The system runs on a DigitalOcean VPS (1-2GB RAM, 1 vCPU, 25GB SSD) using SQLite for persistence, KIMI K2 via NVIDIA API for intelligence, and Google Drive for file storage.

---

## 2. BUSINESS CONTEXT

### 2.1 The Company

**North Star Impex Group** is a manufacturing and distribution conglomerate operating across UAE, India, China, Kenya, and West Africa. Subsidiaries include:

| Entity | Role |
|--------|------|
| North Star Impex (Parent) | Group holding company |
| NSI Projects | Project execution |
| Fine Techno Pack (FTPL) | Tank manufacturing (Imran) |
| Stel Astra Ventures LLP | Indian operations |
| NSI China | Chinese sourcing |
| Pacific Unity MEA FZ-LLC | UAE entity (FZ-LLC) |
| North Star Impex Kenya | East Africa operations |
| North Star Impex West Africa | West Africa operations |

### 2.2 The Problem

All business coordination happens on WhatsApp across multiple group chats. This creates:

1. **Lost tasks:** Verbal assignments ("Pay 25K to Shahid") disappear in chat history
2. **Manual document creation:** Proforma Invoices and Quotations are manually assembled in Word/PDF
3. **No tracking:** Nobody knows which vendor quote is the latest, which drawing was approved, or who owes what
4. **No accountability:** Follow-ups depend on human memory across IST and African timezones
5. **File chaos:** PDFs, CAD drawings, and specs are scattered across WhatsApp chats with no organization

### 2.3 Key Stakeholders

| Person | Role | WhatsApp ID | System Role |
|--------|------|-------------|-------------|
| Dad Africa (Sunil) | Business Owner / Decision Maker | Hardcoded | Admin |
| Shreyas Sunil | Operations Coordinator / System Owner | Hardcoded | Admin |
| Govind | Field Operations / Purchasing | Hardcoded | Employee |
| Shibu | Procurement Team | Hardcoded | Employee |
| Kumutha | Administration | Hardcoded | Employee |
| Imran (Fine Techno Pack) | Manufacturing Partner | Hardcoded | External |
| Karthik | AutoCAD / Technical Drawings | Hardcoded | External |

---

## 3. SYSTEM OVERVIEW

### 3.1 High-Level Flow

```
WhatsApp Users
      │
      ▼
 OpenClaw Tunnel (Webhook POST, 10s timeout)
      │
      ▼
 FastAPI Webhook Handler (ACK in <500ms, enqueue)
      │
      ▼
 Async Task Queue (in-process asyncio queue)
      │
      ├──► Ingress Parser (normalize, PII redact, dedup)
      │         │
      │         ▼
      │    Intent Router (LLM-powered classification)
      │         │
      │         ├──► Task Engine ──► Chaser Cron
      │         ├──► Document Generator ──► Brand Templates
      │         ├──► File Handler ──► Google Drive Sync
      │         ├──► Data Extractor ──► SQLite Graph Tables
      │         └──► Query Responder ──► Context Retrieval
      │
      ▼
 Outbound Gateway (OpenClaw WebSocket)
      │
      ▼
 WhatsApp Users
```

### 3.2 Chat Groups Monitored

| Chat | JID Type | Purpose |
|------|----------|---------|
| Personal (Dad ↔ Shreyas) | DM | Confidential decisions, pricing negotiations |
| Company Main Group | Group | General operations, announcements |
| Company Side Group | Group | Procurement, supplier management |
| Company Project Group | Group | Tank manufacturing, technical specs |

### 3.3 Bot Activation

The bot activates when mentioned with `@nsi` (configurable) followed by a command or intent. Without the tag, the bot passively ingests and indexes messages but does NOT respond or take action.

**Passive mode (always on):** Store messages, extract entities, update graph tables, detect tasks.
**Active mode (on @nsi mention):** Execute commands, generate documents, respond to queries.

---

## 4. FUNCTIONAL REQUIREMENTS

### FR-1: Webhook Ingress & Message Parsing

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Accept OpenClaw webhook POST payloads (WhatsApp Cloud API format wrapped in OpenClaw's `message:received` context) | P0 |
| FR-1.2 | Respond with HTTP 200 within 500ms; enqueue message for async processing | P0 |
| FR-1.3 | Implement idempotency using `messageId` as deduplication key (TTL: 1 hour in SQLite) | P0 |
| FR-1.4 | Parse message types: text, image, audio/voice, video, document, location, contacts | P0 |
| FR-1.5 | For media messages, fetch file using WhatsApp Cloud API media ID endpoint | P0 |
| FR-1.6 | Detect and flag forwarded messages with `is_forwarded` metadata | P1 |
| FR-1.7 | Ignore deleted message placeholders ("This message was deleted") | P1 |
| FR-1.8 | Transcribe voice notes using Whisper (OpenClaw plugin `@agentclaws/openclaw-whisper`) | V2 |
| FR-1.9 | Accept input in English and Hindi; all system output in English | P0 |
| FR-1.10 | Parse group metadata events (member added/removed); confirm with admin before updating roster | P1 |

### FR-2: PII Redaction

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Before storing any message in SQLite, scan for and redact: OTPs (6-digit patterns with "OTP" context), credit card numbers (4-digit suffixed patterns), bank transaction references | P0 |
| FR-2.2 | Store the redacted version in the main `messages` table | P0 |
| FR-2.3 | Optionally store the raw (unredacted) version in a separate encrypted column or skip raw storage entirely | P1 |

### FR-3: Intent Routing

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | When `@nsi` is detected in a message, extract the command/intent and route to the appropriate handler | P0 |
| FR-3.2 | Use KIMI K2 (8K token budget) for intent classification when keyword matching is ambiguous | P0 |
| FR-3.3 | Supported intent categories: `generate_document`, `assign_task`, `query_data`, `upload_file`, `compare_files`, `check_status`, `cancel_task`, `pause_task` | P0 |
| FR-3.4 | For non-@nsi messages: passively store, extract entities, detect implicit task assignments | P0 |
| FR-3.5 | LLM auto-classifies task priority (P0/P1/P2) based on content analysis (financial = P0, operational = P1, administrative = P2) | P0 |

### FR-4: Context Buffer ("The Shopping Cart")

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | When a multi-step intent is detected (e.g., "Compare these quotes"), open a context buffer keyed by `(user_id, chat_id, intent_hash)` | P0 |
| FR-4.2 | Buffer collects subsequent messages/files from the same user in the same chat | P0 |
| FR-4.3 | Buffer closes when user says "Done" or after 10-minute inactivity timeout | P0 |
| FR-4.4 | If user sends a related message after timeout, smart re-open the buffer if the same intent is detected | P1 |
| FR-4.5 | Send confirmation on buffer open: "Got it, I'm collecting files. Send me everything and say 'Done' when ready, or I'll process in 10 minutes." | P0 |
| FR-4.6 | Support unlimited concurrent buffers per user (different chats, different intents) | P0 |
| FR-4.7 | Dashboard shows active buffers and allows manual trigger/close | P1 |

### FR-5: Task Management & The Chaser

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Detect task assignments in messages (both explicit "@nsi assign..." and implicit "Pls pay 25K to Shahid") | P0 |
| FR-5.2 | Store task in SQLite: `assigner`, `assignee`, `description`, `priority` (P0/P1/P2), `status`, `created_at`, `deadline`, `last_nudged_at` | P0 |
| FR-5.3 | Chaser cron loop runs every 1 hour, checking for overdue tasks | P0 |
| FR-5.4 | Quiet window: NO nudges between 2:00 AM - 8:00 AM IST | P0 |
| FR-5.5 | Escalation matrix (from task creation or deadline, whichever is set): | P0 |

**Escalation Matrix:**

| Priority | WhatsApp Nudge | Firm Chase | Email Escalation |
|----------|---------------|------------|------------------|
| P0 (Critical/Financial) | T+2h | T+4h | T+6h |
| P1 (Standard Operations) | T+12h | T+18h | T+24h |
| P2 (Administrative) | T+24h | T+48h | T+72h |

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.6 | Nudge messages use hardcoded templates with variable injection (no LLM call): "Reminder: '{task}' assigned to {person} is overdue by {hours}h. Reply 'done' when complete." | P0 |
| FR-5.7 | Duplicate nudge prevention: enforce minimum 55-minute gap via `last_nudged_at` column | P0 |
| FR-5.8 | Task completion detection: assignee replies with "Done", "Completed", "Paid", "Ok", or similar keywords in the same chat | P0 |
| FR-5.9 | Manual task control via WhatsApp: "Cancel task: {description}" or "Pause task: {description}" from Admin users | P0 |
| FR-5.10 | Manual task control via dashboard: pause, cancel, reassign, change priority | P0 |
| FR-5.11 | Task status queryable via WhatsApp: "@nsi status" returns a summary of all pending tasks | P0 |

### FR-6: Document Generation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | Generate Proforma Invoices from chat commands using DOCX templates | P0 |
| FR-6.2 | Generate Commercial Quotations using DOCX templates | P0 |
| FR-6.3 | Generate Packing Lists using DOCX templates | V1 |
| FR-6.4 | Generate formal documents on company letterhead | V1 |
| FR-6.5 | Support multi-brand templates (Pacific Unity, Stel Astra, NSI Projects, etc.) | V1 |
| FR-6.6 | LLM extracts line items, pricing, terms from conversation context | P0 |
| FR-6.7 | ALL prices pulled from SQLite (graph tables), never from LLM memory | P0 |
| FR-6.8 | Currency: hardcoded exchange rate (INR→USD at 91, configurable). Default output in USD | P0 |
| FR-6.9 | Approval workflow: bot sends draft PDF → user replies "Approved" or "Change X to Y" → bot regenerates or finalizes | P0 |
| FR-6.10 | On approval: upload final document to Google Drive, log in SQLite, send back to chat | P0 |
| FR-6.11 | Self-evaluation: bot scores generated document against template schema. If confidence < 80%, flag for human review instead of auto-sending | P1 |

### FR-7: Google Drive File Sync

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-7.1 | Use Google Service Account authenticated to Shreyas's personal Drive (50GB available) | P0 |
| FR-7.2 | Project-based folder hierarchy (see architecture for structure) | P0 |
| FR-7.3 | On media receipt: download from WhatsApp → write to `/tmp/` → upload to Drive → store Drive link in SQLite → delete local file | P0 |
| FR-7.4 | Duplicate detection by SHA-256 hash. If duplicate found: store new version alongside old, flag in metadata as `duplicate_of: {original_id}` | P1 |
| FR-7.5 | Upload failure: retry 3x with exponential backoff → alert Shreyas on WhatsApp → queue for next cron cycle. NEVER delete local copy until upload confirmed | P0 |
| FR-7.6 | Hourly SQLite backup: upload `.db` file to `System/DB_Backups/` on Drive | P0 |
| FR-7.7 | File retention: permanent (no auto-delete or archival) | P0 |

### FR-8: Email Escalation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-8.1 | Send escalation emails via `info@stelastra.com` using Microsoft 365 OAuth2 (MSAL) | V1 |
| FR-8.2 | Register Azure AD application for OAuth2 token acquisition | V1 |
| FR-8.3 | Email format: plain text | V1 |
| FR-8.4 | CC rules: Shreyas CC'd on ALL escalation emails. Dad Africa CC'd on P0 (critical) escalations only | V1 |
| FR-8.5 | Email content includes: task description, assignee, days overdue, original chat context snippet | V1 |

### FR-9: Employee Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-9.1 | Mobile-first responsive web dashboard | P0 |
| FR-9.2 | Authentication: simple username + password (hardcoded initially in config, one per employee) | P0 |
| FR-9.3 | Task list view: assigned to me, overdue, completed, with filters | P0 |
| FR-9.4 | Chat interface: 1-on-1 conversation with the bot, pre-loaded with user's active tasks | P0 |
| FR-9.5 | Analytics view: tasks per employee, average completion time, bottleneck identification | V1 |
| FR-9.6 | Document search: find any vendor quote, generated invoice, or uploaded file by keyword/date/vendor | P0 |
| FR-9.7 | File upload portal: bypass WhatsApp's 16MB limit, upload directly to correct Drive folder | P1 |
| FR-9.8 | Active context buffer management: view, trigger, or close open buffers | P1 |
| FR-9.9 | Hosted via FastAPI static file serving (simplest, no separate deployment) | P0 |
| FR-9.10 | No crawler indexing: `robots.txt` with `Disallow: /`, `X-Robots-Tag: noindex` header | P0 |

### FR-10: Analytics & Daily EOD Reports

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-10.1 | Daily EOD report generated at 6:00 PM IST | V1 |
| FR-10.2 | Report format: structured text message sent to WhatsApp Main Group | V1 |
| FR-10.3 | Report contents: tasks completed today, tasks overdue, tasks created today, pending document approvals, files uploaded | V1 |
| FR-10.4 | Weekly summary report: aggregated metrics, bottleneck analysis, outstanding items | V1 |
| FR-10.5 | Dashboard analytics: real-time task velocity, per-employee performance, overdue trends | V1 |

### FR-11: Cross-Chat Context & Privacy

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-11.1 | All team members can see all data (no role-based data restriction for queries) | P0 |
| FR-11.2 | Exception: if data originates from a DM/personal chat and is requested from a group, bot asks the DM participant for permission before surfacing | P0 |
| FR-11.3 | Context isolation: each chat maintains its own conversation context buffer | P0 |
| FR-11.4 | Entity data (vendors, prices, tasks) is global — shared across all chats once stored in SQLite | P0 |

### FR-12: Feedback & Self-Evaluation Loop

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-12.1 | For generated documents: bot self-scores against template schema (required fields present, prices match SQLite, totals compute correctly) | P1 |
| FR-12.2 | If self-score ≥ 80%: send to chat for human approval | P1 |
| FR-12.3 | If self-score < 80%: send to chat with explicit warning: "Low confidence on this draft. Please review carefully: {issues}" | P1 |
| FR-12.4 | Log all self-evaluation scores for continuous improvement tracking | P1 |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

### NFR-1: Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | Webhook ACK response time | < 500ms |
| NFR-1.2 | Message processing (parse + store) | < 2s |
| NFR-1.3 | Simple query response (data lookup) | < 5s |
| NFR-1.4 | Document generation (end-to-end) | < 60s (with "Working on it..." acknowledgment) |
| NFR-1.5 | File upload to Drive | < 30s for files under 10MB |
| NFR-1.6 | SQLite query performance | < 50ms for indexed queries |
| NFR-1.7 | Dashboard page load | < 3s |

### NFR-2: Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-2.1 | Uptime | 99% (allows ~7h downtime/month) |
| NFR-2.2 | Zero message loss from idempotency dedup failures | Critical |
| NFR-2.3 | Zero duplicate nudges from Chaser | Critical |
| NFR-2.4 | SQLite backup frequency | Hourly to Google Drive |
| NFR-2.5 | Automatic recovery on crash | systemd + Docker restart policy |

### NFR-3: Security

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-3.1 | VPS: SSH key-only auth, UFW (ports 80/443 only), fail2ban | Required |
| NFR-3.2 | HTTPS via Caddy + Let's Encrypt on `bot.stelastra.com` | Required |
| NFR-3.3 | PII redaction before SQLite storage | Required |
| NFR-3.4 | VPS-level disk encryption | Sufficient (no SQLCipher) |
| NFR-3.5 | API keys stored in environment variables, never in code | Required |
| NFR-3.6 | Dashboard: `robots.txt` Disallow all, `noindex` headers | Required |

### NFR-4: Resource Constraints

| ID | Constraint | Limit |
|----|-----------|-------|
| NFR-4.1 | VPS RAM | 1-2 GB |
| NFR-4.2 | VPS CPU | 1 vCPU |
| NFR-4.3 | VPS Disk | 25 GB SSD |
| NFR-4.4 | Docker total footprint | < 500 MB RAM |
| NFR-4.5 | Log retention | 7 days, max 500 MB, rotated daily |
| NFR-4.6 | NVIDIA API rate limit | 40 RPM (free tier) |
| NFR-4.7 | Google Drive storage | 50 GB (personal account) |

---

## 6. V1 SCOPE DEFINITION

### 6.1 IN V1 (Target: 6-8 weeks)

1. Webhook ingress + message parsing + PII redaction + SQLite storage
2. Intent routing with `@nsi` activation + passive indexing
3. Context buffer for multi-message sessions
4. Task management + Chaser (WhatsApp nudges + email escalation)
5. Document generation: Proforma Invoice, Commercial Quotation, Packing List, Letterhead
6. Google Drive file sync with retry and backup
7. Email escalation via Outlook/MSAL (plain text, CC rules)
8. Employee dashboard (task list, chat interface, document search)
9. Analytics dashboard + daily EOD reports to WhatsApp
10. Cross-chat privacy controls

### 6.2 NOT IN V1 (Deferred)

| Feature | Target Version |
|---------|---------------|
| Full graph RAG querying (natural language over entity graph) | V2 |
| Voice note transcription (Whisper) | V2 |
| Dubizzle/web scraping | V2 |
| CRM/ERP integration via MCP | V2 |
| Auto-generated XLSX weekly reports | V2 |
| Multi-language output (Hindi) | V3 |

### 6.3 Success Criteria (V1 Launch Gate)

All four must pass:

- [ ] Bot successfully parses a real WhatsApp message and stores it in SQLite with PII redacted
- [ ] Bot generates a correct Proforma Invoice from a chat command, approved and uploaded to Drive
- [ ] Bot assigns a task and sends a WhatsApp nudge after the deadline passes
- [ ] A file sent on WhatsApp appears in the correct Google Drive folder within 60 seconds

---

## 7. CONSTRAINTS & DEPENDENCIES

### 7.1 External Dependencies

| Dependency | Status | Risk |
|-----------|--------|------|
| OpenClaw tunnel (open source) | Available | Medium — no persistent inbound queue; need systemd hardening |
| NVIDIA API (KIMI K2) | 5,000 free credits | High — free tier has 40 RPM limit; must implement rate limiter |
| Google Drive API | Available (Service Account) | Low — well-documented, reliable |
| Microsoft 365 (info@stelastra.com) | Available | Medium — requires Azure AD app registration for OAuth2 |
| WhatsApp Cloud API (via OpenClaw) | Available | Medium — rate limits per Meta's tier system |

### 7.2 User Dependencies

| Item | Owner | Deadline |
|------|-------|----------|
| Upload DOCX templates (PI, Quotation, Packing List, Letterhead) to workspace | Shreyas | Before V1 document generation sprint |
| Upload brand assets (logos for each subsidiary, colors, fonts) | Shreyas | Before V1 document generation sprint |
| Create DNS A record: `bot.stelastra.com` → VPS IP | Shreyas | Before V1 deployment |
| Share Google Drive folder with Service Account email | Shreyas | Before V1 Drive sync sprint |
| Register Azure AD app for MSAL OAuth2 | Shreyas (guided) | Before V1 email sprint |
| Provide hardcoded employee phone→name JSON mapping | Shreyas | Before V1 ingress sprint |

---

## 8. RISKS & MITIGATIONS

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| NVIDIA API free credits exhausted | Bot goes silent | High | Fallback chain: KIMI K2 → GPT-4o-mini → Claude Haiku. Token usage tracking with alerts at 80% spend |
| OpenClaw crashes, messages lost | Missed tasks/files | Medium | systemd auto-restart, UptimeRobot monitoring, WhatsApp heartbeat check |
| SQLite corruption from concurrent writes | Data loss | Medium | WAL mode, single-writer queue, hourly Drive backups |
| LLM hallucinates pricing on invoice | Wrong invoice sent to client | High | Strict template + SQLite price lookup + human approval gate |
| VPS disk fills up | System crash | Medium | Drive sync with local cleanup, log rotation (7-day, 500MB cap), hourly DB backup offload |
| WhatsApp rate limit / ban | Bot can't send messages | Low | Exponential backoff, throttle queue, auto-shift to email |

---

*This PRD is LOCKED. Changes require a versioned amendment with stakeholder sign-off.*
