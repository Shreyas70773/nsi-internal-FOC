# NSI Internal System (FOC) - WhatsApp-Native Agentic Business Operations Bot

[![GitHub](https://img.shields.io/badge/GitHub-nsi--internal--FOC-blue)](https://github.com/Shreyas70773/nsi-internal-FOC.git)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Language](https://img.shields.io/badge/Language-Python%203.10%2B-blue)
![License](https://img.shields.io/badge/License-Proprietary-red)

**A hierarchical multi-agent AI system that transforms chaotic WhatsApp business communications into automated, auditable workflows for manufacturing operations.**

---

## 📋 Overview

NSI Internal FOC (Federal Order of Control) is an enterprise-grade, WhatsApp-native automation platform designed for **Pacific Unity MEA FZ-LLC** and **STEL Astra Ventures LLP**. It converts unstructured group chat threads into actionable business intelligence, task assignments, and auto-generated documents.

### Core Capabilities

1. **Intelligent Chat Ingestion:** Parses messy, multi-user WhatsApp histories with attachments (PDFs, Word docs, Excel sheets).
2. **Hierarchical Sub-Agent Execution:** Routes specific business workflows to specialized domain agents (Procurement, Finance, Operations, Engineering).
3. **Autonomous Task Chasing:** Tracks pending work across distributed teams (India, Africa) with automatic WhatsApp nudges and email escalations.
4. **Knowledge Graph & RAG:** Maintains a localized Graph database mapping Vendors → Quoted → Parts → Pricing for instant retrieval.
5. **Document Mastery:** Auto-generates Proforma Invoices, Commercial Quotations, and Formal Letterheads using company templates.
6. **Employee Dashboards:** Individual web dashboards showing task urgency, deadlines, and real-time chaser status.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        WhatsApp (OpenClaw Tunnel)           │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│              Router Agent (Context Buffer)                   │
│  • Batches multi-file uploads (Session Management)          │
│  • Intent Classification & Trigger Detection                │
└────────────┬────────────────────────────────────────────────┘
             │
      ┌──────┴──────────────────────────────┐
      │                                      │
┌─────▼──────────────────┐      ┌──────────▼──────────────┐
│  Supervisor Agents     │      │  Background Services   │
│  • Procurement         │      │  • The Chaser (Cron)   │
│  • Finance             │      │  • Context Condenser   │
│  • Operations          │      │  • Graph Indexer       │
│  • Engineering         │      │  • Email Escalator     │
└─────┬──────────────────┘      └──────────┬──────────────┘
      │                                    │
      └────────────┬─────────────────────┬─┘
                   │                     │
        ┌──────────▼──────────┐ ┌───────▼─────────┐
        │  Skills Layer       │ │ Data Layer      │
        │ • docx (Word gen)   │ │ • SQLite (+RAG) │
        │ • pdf (parsing)     │ │ • Google Drive  │
        │ • xlsx (tabulation) │ │ • Cache (Redis) │
        │ • mcp-builder       │ │ • SMTP (Email)  │
        └────────────────────┘ └─────────────────┘
```

### Key Design Decisions

- **Lightweight VPS Footprint:** Designed for DigitalOcean GitHub Student VPS (1-2GB RAM, 1 vCPU).
- **SQLite + JSON:** Graph RAG emulated via SQLite with JSON extensions (no Neo4j overhead).
- **Embedded Scheduler:** APScheduler for the Chaser cron loop (no Temporal.io complexity).
- **Native Tool Calling:** NVIDIA KIMI K2 supports OpenAI-compatible function calling natively.
- **Stateless & Resilient:** Horizontal scaling ready despite running monolithically on single VPS.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Docker & Docker Compose** (recommended)
- **API Keys:**
  - NVIDIA API Key (KIMI K2)
  - OpenAI API Key (Fallback LLM)
  - Google Service Account credentials (Drive storage)
  - Microsoft 365 OAuth2 credentials (Email escalation)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/Shreyas70773/nsi-internal-FOC.git
   cd nsi-internal-FOC
   ```

2. **Set Up Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   nano .env
   ```

3. **Install Dependencies** (Local Development)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run with Docker** (Recommended for Production)
   ```bash
   docker-compose up --build -d
   ```
   The application will be accessible at `http://localhost:8000`.

5. **Verify Health**
   ```bash
   curl http://localhost:8000/api/health
   ```

---

## 📁 Project Structure

```
nsi-internal-FOC/
├── app/                              # FastAPI application
│   ├── main.py                       # Entry point
│   ├── api/
│   │   ├── webhooks.py              # OpenClaw webhook handlers
│   │   ├── health.py                # Health check endpoint
│   │   └── dashboard.py             # Employee dashboard routes
│   ├── agents/
│   │   ├── router.py                # Intent classification & routing
│   │   ├── supervisors/
│   │   │   ├── procurement.py       # Procurement Supervisor
│   │   │   ├── finance.py           # Finance Supervisor
│   │   │   ├── operations.py        # Operations Supervisor
│   │   │   └── engineering.py       # Engineering Supervisor
│   │   └── services/
│   │       ├── chaser.py            # The Chaser (task following)
│   │       ├── context_buffer.py    # Session/file batching
│   │       ├── graph_indexer.py     # Knowledge Graph maintenance
│   │       └── email_escalator.py   # Formal email pipeline
│   ├── skills/                      # MCP-wrapped skill executors
│   │   ├── docx_executor.py         # Word document generation
│   │   ├── pdf_executor.py          # PDF parsing & merging
│   │   └── xlsx_executor.py         # Spreadsheet manipulation
│   ├── llm/
│   │   ├── nvidia_client.py         # KIMI K2 via NVIDIA API
│   │   ├── openai_client.py         # OpenAI fallback
│   │   └── anthropic_client.py      # Anthropic fallback
│   ├── db/
│   │   ├── models.py                # SQLite ORM/schemas
│   │   ├── graph.py                 # Graph RAG query logic
│   │   └── migrations.py            # Database initialization
│   ├── integrations/
│   │   ├── google_drive.py          # Google Drive sync
│   │   ├── outlook_email.py         # Microsoft 365 SMTP
│   │   └── openclaw.py              # OpenClaw WebSocket client
│   └── config.py                    # Pydantic settings
├── config/                          # User-editable configurations
│   ├── employee_mapping.json        # WhatsApp # → Employee mapping
│   ├── supervisor_prompts.yaml      # Supervisor system prompts
│   └── escalation_rules.yaml        # Chaser SLA rules
├── data/                            # Runtime data (SQLite, Cache)
│   └── nsi.db                       # SQLite database
├── templates/                       # Jinja2 templates
│   ├── documents/
│   │   ├── proforma_invoice.docx    # Invoice template
│   │   ├── quotation.docx           # Quotation template
│   │   └── letterhead.docx          # Company letterhead
│   └── dashboards/
│       ├── task_board.html          # Employee task dashboard
│       └── analytics.html           # Admin analytics
├── credentials/                     # (Gitignored) API keys & certs
│   └── gdrive-sa.json               # Google Service Account
├── .env                             # (Gitignored) Real environment vars
├── .env.example                     # Template with placeholders
├── .gitignore                       # Excludes sensitive files
├── docker-compose.yml               # Production Docker config
├── Dockerfile                       # Container image spec
├── requirements.txt                 # Python dependencies
├── Caddyfile                        # Reverse proxy config (TLS)
└── README.md                        # This file
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in actual values:

```dotenv
# LLM Providers
NVIDIA_API_KEY=nvapi-...             # Primary LLM
OPENAI_API_KEY=sk-proj-...           # Fallback LLM
ANTHROPIC_API_KEY=sk-ant-...         # Secondary fallback

# Google Drive
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/gdrive-sa.json
GOOGLE_DRIVE_ROOT_FOLDER_ID=...      # Root folder ID in Drive

# Email (Microsoft 365 OAuth2)
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_TENANT_ID=...
EMAIL_FROM=info@stelastra.com
EMAIL_ALWAYS_CC=shreyas@finetechnopack.com
EMAIL_P0_CC=sunil@finetechnopack.com

# OpenClaw WebSocket
OPENCLAW_WS_URL=ws://localhost:3000/gateway
OPENCLAW_API_KEY=...

# Database
DB_PATH=data/nsi.db

# Bot Behavior
BOT_MENTION_TAG=@nsi
QUIET_WINDOW_START_HOUR=2            # No chasing 2-8 AM (in case of tz drift)
QUIET_WINDOW_END_HOUR=8
CHASER_INTERVAL_MINUTES=60           # Run chaser every 60 minutes
CONTEXT_BUFFER_TIMEOUT_MINUTES=10    # Clear buffer after 10 min silence

# Dashboard
DASHBOARD_SECRET_KEY=...             # Random 64-char string for sessions
DASHBOARD_SESSION_HOURS=24           # Session validity

# Webhooks
WEBHOOK_PATH=/api/webhook
IDEMPOTENCY_TTL_SECONDS=3600         # Prevents duplicate processing
```

**⚠️ IMPORTANT:** Never commit `.env` to git. It will be automatically .gitignored.

---

## 🤖 Agent Architecture & Workflows

### The Router Agent
Acts as the intelligent dispatcher. Upon receiving a WhatsApp message:
1. Extracts intent (Is this a task? A document request? A status update?).
2. Maintains a **Context Buffer** to batch multi-file uploads.
3. Delegates work to the appropriate Supervisor Agent.

### Sub-Agent Types

**Procurement Supervisor**
- Detects vendor quotes and pricing updates.
- Uses `pdf` skill to parse quotation sheets.
- Auto-appends extracted data to the Supplier Management Google Sheet.
- Triggers alerts if pricing deviates >5% from historical norms.

**Finance Supervisor**
- Receives raw line items and generates formal Proforma Invoices.
- Uses `docx` + `brand-guidelines` skills for letterhead & formatting.
- Parses payment terms and validates against historical precedent.

**Operations Supervisor**
- Identifies task assignments ("Pls pay X to Shahid", "Get video from Govind").
- Delegates to the **Chaser** service to track & escalate.
- Reports on task velocity to the Admin Dashboard.

**Engineering Supervisor**
- Processes technical drawings and specifications (Autocad PDFs).
- Cross-references nozzle orientations, tank dimensions, electrical specs.
- Alerts on specification conflicts or missing data points.

### The Chaser Service (Background Cron)

Runs every 60 minutes, scanning the SQLite task table for pending items:

| Deadline Status | Action | Delay |
| :--- | :--- | :--- |
| **In Progress** | WhatsApp nudge | T-4h before deadline |
| **Overdue by 2h** | Firm WhatsApp message | T+2h |
| **Overdue by 12h+** | Formal Email • CC Manager | T+12h |
| **Overdue by 48h+** | Executive Alert | T+48h |

---

## 📊 Knowledge Graph & RAG

The system maintains a relational "Graph" stored in SQLite:

```sql
-- Simplified schema
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    type TEXT,                     -- "Vendor", "Employee", "Part", "Company"
    name TEXT,
    metadata JSON
);

CREATE TABLE relationships (
    source_id INTEGER,
    target_id INTEGER,
    relation_type TEXT,            -- "Quoted", "Employed_By", "PartOf"
    metadata JSON,
    created_at TIMESTAMP
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER,
    file_name TEXT,
    gdrive_url TEXT,
    extracted_summary TEXT,        -- Vector DB or plain text
    created_at TIMESTAMP
);
```

When an agent asks *"What was Imran's quote for the Zincalume tank?"*, the Router queries:
```
Vendor(Imran) -> Edge(Quoted_For) -> Part(Zincalume Tank) -> Edge(Priced_At) -> Value(₹1137/kg)
```

---

## 🌐 Employee Dashboards

Lightweight, crawl-protected static/dynamic HTML dashboards serve each employee their personal task board:

- **Urgency Matrix:** Standard, Overdue, Manager-Escalated tasks.
- **Upload Portal:** Direct file uploads bypassing WhatsApp's media limits.
- **Agent Chat:** 1-on-1 conversation with sub-agents for task help.
- **SLA Tracking:** Real-time display of chase timers and escalation status.

Accessed via magic links in daily WhatsApp messages:
```
Good morning Govind, here is your agenda: 
https://internal.nsi-bot.com/dashboard/govind/abc123token
```

---

## 🔐 Security & Compliance

- **.env is gitignored:** Real API keys never committed to version control.
- **HTTPS/TLS Enforced:** Caddy reverse proxy handles SSL termination.
- **Rate Limiting:** 100 req/min per IP on webhook endpoints.
- **CSRF Protection:** JWT tokens for dashboard sessions.
- **Audit Logging:** All task changes logged with timestamps and operator names.
- **User Privacy:** Employee phone numbers hashed; real numbers stored only in `.env`.

---

## 🛠️ Development & Testing

### Local Development
```bash
python venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

### Testing with Docker
```bash
docker-compose -f docker-compose.test.yml up
```

### Sample API Calls

**Webhook (WhatsApp Message)**
```bash
curl -X POST http://localhost:8000/api/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "wamid.XXX",
    "from": "+971501234567",
    "text": "Check the pricing from Imran",
    "attachments": [
      {"type": "document", "url": "https://example.com/quote.pdf"}
    ]
  }'
```

**Health Check**
```bash
curl http://localhost:8000/api/health
```

**Dashboard Access**
```
http://localhost:8000/dashboard/govind/?token=abc123
```

---

## 📈 Monitoring & Logging

The application logs to:
- **Console:** Real-time activity during development.
- **SQLite:** Persistent event log in `data/nsi.db` table `event_logs`.
- **Google Drive:** Weekly audit reports synced automatically.

Monitor task velocity, chaser effectiveness, and API call latencies via the admin dashboard at:
```
http://localhost:8000/admin/analytics
```

---

## 🚨 Troubleshooting

| Issue | Resolution |
| :--- | :--- |
| **API Key Errors** | Verify `.env` is populated and valid. Check NVIDIA/OpenAI dashboard for rate limits. |
| **Google Drive Sync Fails** | Confirm Service Account JSON exists at `credentials/gdrive-sa.json` and has Drive API enabled. |
| **Email Won't Send** | Check Microsoft 365 OAuth credentials. Verify inbox rules don't block `info@stelastra.com`. |
| **Database Lock (SQLite)** | Ensure only one Docker container instance is running. Restart with `docker-compose restart`. |
| **Context Buffer Filling Up** | Reduce `CONTEXT_BUFFER_TIMEOUT_MINUTES` in `.env` (default 10 min). |

---

## 📚 Documentation

- **[Architecture Whitepaper V2](ARCHITECTURE_WHITEPAPER_V2.md):** Deep dive on the multi-agent hierarchy and context buffer design.
- **[System Design Spec](SYSTEM_DESIGN_ENGINEERING_SPEC.md):** Enterprise design patterns, fault tolerance, and edge cases.
- **[Project Analysis](PROJECT_ANALYSIS_CLEAN.md):** Business requirements extracted from WhatsApp chat histories.
- **[Master Analyzer Prompt](MASTER_ANALYZER_PROMPT.md):** The ingestion template for new workflow discovery.
- **[Discovery & PRD](discovery.md, PRD.md):** Scoping questionnaire and finalized product requirements.

---

## 🤝 Contributing

As of March 18, 2026, this is proprietary software for **NSI / Pacific Unity MEA FZ-LLC**. External contributions are not accepted. For internal improvements, please:

1. Create a feature branch: `git checkout -b feature/my-enhancement`
2. Write tests in `tests/` directory.
3. Submit a pull request with detailed commit messages.
4. Ensure all secrets remain in `.env` (never `.env.example`).

---

## 📞 Support & Escalation

**For bugs/issues:** Contact Shreyas Sunil (Ops Lead)  
**For vendor integrations:** Contact Dad Africa (Business Owner)  
**For technical architecture:** Refer to the engineering whitepaper above.

---

## 📄 License

**Proprietary.** All rights reserved. Unauthorized distribution or modification is prohibited.

---

**Last Updated:** March 18, 2026  
**Repository Owner:** Shreyas Sunil  
**Organization:** NSI / Pacific Unity MEA FZ-LLC
