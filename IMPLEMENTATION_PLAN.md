# IMPLEMENTATION PLAN
## NSI Bot — V1 Build Schedule

| Field | Value |
|-------|-------|
| **Total Duration** | 8 weeks |
| **Start Date** | March 18, 2026 (Tuesday) |
| **Target V1 Launch** | May 12, 2026 (Tuesday) |
| **Developer** | AI-assisted (Cursor + Shreyas oversight) |
| **Testing** | Shreyas (sole tester for V1) |

---

## PHASE 0: FOUNDATION (Week 1 — Mar 18-24)

**Goal:** Skeleton app running in Docker, accepting webhooks, storing messages.

| Day | Task | Deliverable | Blocked By |
|-----|------|-------------|------------|
| 1 | Project scaffolding: FastAPI app, Docker, docker-compose, Caddyfile, .env.example, requirements.txt | Runnable skeleton | Nothing |
| 1 | SQLite setup: WAL mode, connection pool, migration runner, initial schema (001_initial.sql) | Database ready | Nothing |
| 2 | Webhook handler: POST /api/webhook, payload validation, idempotency check, async queue | Webhook accepts & deduplicates | Nothing |
| 2 | Ingress parser: normalize WhatsApp Cloud API payload → InternalMessage format | Parsed messages in SQLite | Nothing |
| 3 | PII redaction engine: regex-based OTP, card, bank ref detection + redaction | Redacted messages stored | Nothing |
| 3 | Employee registry: hardcoded JSON → SQLite employees table on startup | Employee lookup working | Shreyas provides phone→name map |
| 4 | Health endpoint: GET /api/health (uptime, DB size, disk free) | Monitoring endpoint live | Nothing |
| 4 | Local Docker test: full docker-compose up, send test webhook via curl | End-to-end smoke test | Nothing |
| 5 | Buffer day / catch-up / early start on Week 2 | — | — |

**Week 1 Deliverables:**
- [ ] FastAPI app in Docker accepting webhooks
- [ ] Messages parsed, PII-redacted, stored in SQLite
- [ ] Health endpoint returning system status
- [ ] docker-compose.yml + Caddyfile ready for VPS

**User Action Required (before Week 1 ends):**
- [ ] Provide hardcoded employee phone→name JSON mapping
- [ ] Confirm VPS is provisioned and accessible via SSH

---

## PHASE 1: INTELLIGENCE LAYER (Week 2 — Mar 25-31)

**Goal:** LLM gateway operational, intent routing working, passive entity extraction.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | LLM Gateway: KIMI K2 client via OpenAI SDK, token bucket rate limiter (40 RPM) | LLM calls working |
| 1 | Fallback chain: KIMI K2 → GPT-4o-mini → Claude Haiku with retry logic | Resilient LLM access |
| 2 | Token usage tracker: log provider, model, tokens, latency, cost to SQLite | Cost monitoring |
| 2 | Intent router (Stage 1): rule-based keyword matching for @nsi commands | Fast routing for known commands |
| 3 | Intent router (Stage 2): LLM classification for ambiguous messages (8K budget) | Full routing coverage |
| 3 | Passive entity extractor: detect vendors, prices, specs, projects in non-@nsi messages | Graph tables populated |
| 4 | Context buffer manager: open/collect/timeout/close state machine | Multi-message sessions working |
| 4 | Buffer re-open logic: detect same intent after timeout | Smart buffer behavior |
| 5 | Integration test: send sequence of messages, verify routing + entity extraction + buffering | End-to-end intelligence test |

**Week 2 Deliverables:**
- [ ] LLM calls with rate limiting and fallback
- [ ] Intent routing (rules + LLM) classifying messages correctly
- [ ] Entity extraction populating graph tables
- [ ] Context buffers collecting multi-message sessions

---

## PHASE 2: TASK ENGINE & CHASER (Week 3 — Apr 1-7)

**Goal:** Tasks detected, stored, and followed up with WhatsApp nudges.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Task engine: create tasks from explicit @nsi commands | Task CRUD in SQLite |
| 1 | Implicit task detection: LLM extracts tasks from passive messages ("Pay 25K to Shahid") | Auto-task creation |
| 2 | Priority auto-classification: LLM assigns P0/P1/P2 based on content | Priority tagging |
| 2 | Task state machine: pending → nudged_1 → nudged_2 → escalated → completed/cancelled/paused | Full lifecycle |
| 3 | Chaser cron: APScheduler job (1h interval), quiet window (2-8 AM IST), overdue query | Cron loop running |
| 3 | Nudge templates: gentle, firm message templates with variable injection | Template strings |
| 3 | Duplicate nudge prevention: last_nudged_at with 55-min gap enforcement | No double nudges |
| 4 | WhatsApp outbound: connect to OpenClaw Gateway WebSocket, send text messages | Outbound messaging working |
| 4 | Task completion detection: parse "done"/"ok"/"completed" replies, update task status | Tasks closeable |
| 5 | Manual task control: "@nsi cancel task X", "@nsi pause task X" from WhatsApp | Admin overrides working |
| 5 | Task status query: "@nsi status" returns pending tasks summary | Status queryable |

**Week 3 Deliverables:**
- [ ] Tasks auto-detected from conversation
- [ ] Chaser sends WhatsApp nudges on schedule with quiet window
- [ ] Tasks completable via keyword reply
- [ ] Manual pause/cancel via WhatsApp command

**User Action Required:**
- [ ] OpenClaw installed and running on VPS (or local for testing)
- [ ] WhatsApp number linked to OpenClaw

---

## PHASE 3: FILE SYNC & DRIVE (Week 4 — Apr 8-14)

**Goal:** Files from WhatsApp land in organized Google Drive folders.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Google Drive client: Service Account auth, folder CRUD, resumable upload | Drive API connected |
| 1 | Folder hierarchy bootstrap: create project-based structure on first run | Drive folders ready |
| 2 | Media download: fetch files from WhatsApp Cloud API using media_id | Files downloaded to /tmp/ |
| 2 | File categorization: LLM classifies file → project + subfolder (8K budget) | Auto-categorization |
| 3 | Upload pipeline: download → hash → dedup check → upload → store link → delete local | Full pipeline working |
| 3 | Upload retry: 3x exponential backoff → WhatsApp alert → queue for cron | Failure recovery |
| 4 | Duplicate detection: SHA-256 hash comparison, flag duplicates in metadata | Dedup working |
| 4 | DB backup cron: hourly SQLite upload to System/DB_Backups/ on Drive | Backups running |
| 5 | Integration test: send file via WhatsApp, verify it appears in correct Drive folder | End-to-end file sync |

**Week 4 Deliverables:**
- [ ] Files auto-uploaded to categorized Drive folders
- [ ] Duplicate detection and flagging
- [ ] Hourly database backups to Drive
- [ ] Upload failure recovery with alerts

**User Action Required (before Week 4):**
- [ ] Create Google Cloud project and Service Account (guided)
- [ ] Share Drive folder with Service Account email
- [ ] Place gdrive-sa.json on VPS

---

## PHASE 4: DOCUMENT GENERATION (Week 5 — Apr 15-21)

**Goal:** Bot generates Proforma Invoices, Quotations, and Packing Lists from chat commands.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Template engine: load DOCX templates, inject variables via python-docx | Template injection working |
| 1 | PDF conversion: libreoffice --headless DOCX→PDF pipeline | PDF output working |
| 2 | Variable extraction: LLM extracts line items, pricing, terms from conversation (32K budget) | Structured data from chat |
| 2 | Price validation: cross-reference LLM output against SQLite entity/pricing data | No hallucinated prices |
| 3 | Self-evaluator: score generated doc (required fields, math validation, price verification) | Confidence scoring |
| 3 | Approval workflow: send draft → wait for "Approved"/"Change X" → finalize or regenerate | Human-in-the-loop gate |
| 4 | Multi-brand support: select template based on brand context (Pacific Unity, Stel Astra, etc.) | Brand switching |
| 4 | Currency handling: hardcoded INR→USD rate (91), format output in USD | Currency conversion |
| 5 | Upload approved docs to Drive (Generated_Documents/ folder), log in SQLite | Full document lifecycle |

**Week 5 Deliverables:**
- [ ] Proforma Invoice generation from chat command
- [ ] Commercial Quotation generation
- [ ] Price validation against database (no hallucination)
- [ ] Approval workflow (draft → approve → finalize)
- [ ] Generated docs uploaded to Drive

**User Action Required (before Week 5):**
- [ ] Upload DOCX templates to templates/ directory
- [ ] Upload brand assets (logos, colors) to templates/shared/

---

## PHASE 5: EMAIL & DASHBOARD (Week 6 — Apr 22-28)

**Goal:** Email escalation working. Employee dashboard live.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | MSAL OAuth2 setup: Azure AD app registration, token acquisition | Email auth working |
| 1 | Email service: compose plain text escalation, send via Microsoft Graph or SMTP | Emails sending |
| 1 | CC rules: Shreyas always CC'd, Dad Africa on P0 only | CC logic |
| 2 | Wire Chaser → Email: escalation phase triggers email instead of WhatsApp | End-to-end escalation |
| 2 | Dashboard scaffold: Preact + HTM (no build), mobile-first layout, auth page | Dashboard skeleton |
| 3 | Dashboard auth: username/password login, session tokens, bcrypt password hashing | Auth working |
| 3 | Task list view: API integration, filters (status, assignee, priority) | Tasks visible |
| 4 | Document search: keyword search across documents table, Drive link display | Search working |
| 4 | Chat interface: WebSocket or polling-based 1-on-1 bot chat from dashboard | Chat working |
| 5 | Task management: pause, cancel, reassign, change priority from dashboard | Full task control |

**Week 6 Deliverables:**
- [ ] Email escalation firing from Chaser
- [ ] Dashboard: login, task list, document search, chat interface
- [ ] Mobile-responsive design

**User Action Required (before Week 6):**
- [ ] Register Azure AD app (guided walkthrough provided)
- [ ] Confirm info@stelastra.com SMTP access

---

## PHASE 6: ANALYTICS & EOD (Week 7 — Apr 29 - May 5)

**Goal:** Analytics dashboard live. Daily EOD reports sent to WhatsApp.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Analytics API: task velocity, per-employee metrics, bottleneck detection | Analytics endpoints |
| 1 | Analytics dashboard view: charts (completion rate, overdue trends, average time) | Visual analytics |
| 2 | EOD report generator: aggregate day's tasks (completed, created, overdue, files uploaded) | Report data |
| 2 | EOD cron: APScheduler fires at 6 PM IST, sends structured text to Main Group | Daily report live |
| 3 | Weekly summary: aggregated metrics, top bottlenecks, outstanding items | Weekly report |
| 3 | File upload portal: dashboard page for uploading files directly to Drive | Upload portal |
| 4 | Context buffer management: dashboard page showing active buffers, manual trigger/close | Buffer UI |
| 4 | Cross-chat privacy: permission request flow (bot asks data owner before surfacing DM data in group) | Privacy controls |
| 5 | Log rotation cron: daily rotation, 7-day retention, upload old logs to Drive | Log management |
| 5 | WhatsApp heartbeat: hourly health message to private chat | Heartbeat monitoring |

**Week 7 Deliverables:**
- [ ] Analytics dashboard with employee performance metrics
- [ ] Daily EOD report to WhatsApp Main Group at 6 PM IST
- [ ] Weekly summary report
- [ ] File upload portal on dashboard
- [ ] Cross-chat privacy permission flow

---

## PHASE 7: DEPLOYMENT & LAUNCH (Week 8 — May 6-12)

**Goal:** Deploy to VPS, connect to real WhatsApp, run acceptance tests, launch V1.

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | VPS setup: SSH hardening, UFW, fail2ban, Docker install | Secure VPS |
| 1 | DNS: A record for bot.stelastra.com → VPS IP | Domain pointing |
| 2 | Deploy: git clone, docker-compose up, Caddy auto-SSL | App live on HTTPS |
| 2 | OpenClaw setup: install on VPS, link WhatsApp number, configure webhook URL | Tunnel connected |
| 3 | UptimeRobot: configure monitor for /api/health | External monitoring |
| 3 | Smoke test: send real WhatsApp message → verify parsing, storage, response | Basic flow works |
| 4 | Acceptance test 1: Generate Proforma Invoice from chat command | Success criterion (b) |
| 4 | Acceptance test 2: Assign task, wait for nudge after deadline | Success criterion (c) |
| 5 | Acceptance test 3: Send file on WhatsApp, verify Drive upload within 60s | Success criterion (d) |
| 5 | Acceptance test 4: Verify email escalation fires correctly | Email working |
| 5 | V1 LAUNCH | Production live |

**Week 8 Deliverables:**
- [ ] Bot live on bot.stelastra.com, connected to real WhatsApp
- [ ] All 4 success criteria passing
- [ ] Monitoring active (UptimeRobot + WhatsApp heartbeat)
- [ ] Database backups running to Drive

---

## V1 SUCCESS CRITERIA (Launch Gate)

All four must pass before declaring V1 live:

| # | Criterion | How to Verify |
|---|-----------|---------------|
| 1 | Bot parses a real WhatsApp message and stores it with PII redacted | Check SQLite: message exists, OTP/card refs redacted |
| 2 | Bot generates a correct Proforma Invoice from "@nsi generate PI for 3M tank" | PDF matches template, prices from DB not hallucinated, approval flow works |
| 3 | Bot assigns a task and sends a WhatsApp nudge after deadline | Create task, wait for nudge, verify timing and quiet window respected |
| 4 | File sent on WhatsApp appears in correct Drive folder within 60 seconds | Send PDF, check Drive folder, verify metadata in SQLite |

---

## POST-V1 ROADMAP

| Version | Features | Target |
|---------|----------|--------|
| V1.1 | Bug fixes, performance tuning, template refinements | May 2026 |
| V2.0 | Full graph RAG querying, voice note transcription (Whisper), auto XLSX reports | July 2026 |
| V2.5 | Dubizzle/web scraping, CRM/ERP MCP integration | September 2026 |
| V3.0 | Multi-language output (Hindi), advanced analytics, mobile app | November 2026 |

---

## DEPENDENCY CHECKLIST (User Action Items)

These items must be completed by the dates indicated or the corresponding phase will be blocked.

| Item | Owner | Deadline | Phase Blocked |
|------|-------|----------|---------------|
| Hardcoded employee phone→name JSON | Shreyas | Mar 20 | Phase 0 |
| VPS provisioned + SSH access | Shreyas | Mar 24 | Phase 7 |
| OpenClaw installed + WhatsApp linked | Shreyas | Apr 1 | Phase 2 |
| Google Cloud Service Account + gdrive-sa.json | Shreyas (guided) | Apr 7 | Phase 3 |
| Share Drive folder with Service Account | Shreyas (guided) | Apr 7 | Phase 3 |
| DOCX templates uploaded | Shreyas | Apr 14 | Phase 4 |
| Brand assets (logos, colors) uploaded | Shreyas | Apr 14 | Phase 4 |
| Azure AD app registered for MSAL | Shreyas (guided) | Apr 21 | Phase 5 |
| DNS A record: bot.stelastra.com → VPS IP | Shreyas (guided) | May 5 | Phase 7 |

*Each "guided" item will have a step-by-step walkthrough provided before its deadline.*

---

*This plan is a living document. Weekly progress reviews will adjust scope if needed.*
