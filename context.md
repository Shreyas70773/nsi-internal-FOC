# PROJECT HANDOFF & CONTEXT DOCUMENT (v2.0)

**Notice to the New LLM/AI Agent:** 
You are being initialized into a highly complex, partially completed Systems Architecture workflow. Your primary objective right now is not to generate code, but to **read and absorb** the work that has already been documented in this workspace, evaluate the primitive initial scoping we did, and then **generate a significantly more advanced layout/questionnaire** for proper enterprise-tier system design.

---

## 1. DIRECTORY MAP & REQUIRED READING (Read these first!)
Before making ANY assumptions about the stack, you must use your file/search APIs to read the following context files in the `C:\Users\bukka\federal-order-of-control` directory:

1. **`I have an idea.md`**: Shows the raw, unbroken "shabby" text dump from WhatsApp. You *must* read this to understand the formatting madness (multi-line breaks without timestamps, inline attachments) your ingress parser will deal with.
2. **`PROJECT_ANALYSIS_CLEAN.md`**: The normalized extraction of `I have an idea.md`. It explains the business context (Pacific Unity MEA FZ-LLC, the actors: Dad Africa, Govind, Imran, the physical products: 3M liter Zincalume tanks).
3. **`WHATSAPP_BOT_ORCHESTRATION_SPEC.md`**: The subagent topology (Ingress Ear -> Librarian Graph Indexer -> Manager Chaser -> Commercial Generation Clerk).
4. **`ARCHITECTURE_WHITEPAPER_V2.md`**: The blueprint mapping the visual HMAS (Hierarchical Multi-Agent System) diagram the user uploaded. Establishes the "Context Buffer" to solve WhatsApp's 1-file-per-webhook limitation.
5. **`SYSTEM_DESIGN_ENGINEERING_SPEC.md`**: The hardcore persistence layer design. Defines the 3-Tier memory pipeline, the Temporal.io / SQLite "Chaser" state machine for follow-ups, and rate-limit fallbacks.
6. **`MASTER_ANALYZER_PROMPT.md`**: The system prompt designed for a sub-agent whose job is to detect "implicit workflows" in future raw chat logs.
7. **`discovery.md`**: Contains the user's initial answers regarding constraints (e.g., using a 1GB DO VPS, Kimi K2 via NVIDIA API, SQLite).

---

## 2. THE "SKILLS" TOOLKIT (mcp/skills)
The user has a robust suite of Markdown-based agent skill instructions located in `skills-main/skills/*`. These act as system prompts/SOPs for tools. You must understand they exist:

*   **`docx` / `pdf` / `xlsx`**: Used by the Sub-Agents to read vendor quotes, draft Proforma Invoices, and tabulate Supplier Google Sheets without hallucinating.
*   **`mcp-builder` & `claude-api`**: Used to wrap new capabilities into OpenClaw routers.
*   **`skill-creator`**: Gives the bot autonomy to write tests and evaluate itself when a new capability is requested.
*   **`brand-guidelines` / `theme-factory`**: Enforces strict styling (e.g., Pacific Unity's letterhead) on all auto-generated documents.

---

## 3. BUSINESS CONTEXT & USE CASE SUMMARY

**The Mission:**
Build a resilient WhatsApp-native business operations bot using **OpenClaw** as a tunnel. 

**Core Responsibilities:**
1. **Parse & Ingest:** Digestion of messy, continuous WhatsApp chat dumps from Personal, Main Company, and Project chats.
2. **"The Chaser" (Project Management):** Autonomously track who is assigned what task. If deadlines pass (operating 24/7 across African and Indian timezones), automatically ping employees via WhatsApp, escalating to Outlook SMTP if unacknowledged.
3. **Document Mastery:** Combine vendor quotes (PDFs), calculate margins, and output formal Commercial Quotations (DOCX).
4. **Knowledge Retrieval:** Use a localized Graph DB mapping (e.g., `Vendor -> Quoted -> Part -> Price`) to instantly answer: *"What was the price Imran quoted?"*

---

## 4. INFRASTRUCTURE & TECHNICAL CONSTRAINTS (Crucial)
The user has confirmed these constraints in `discovery.md`:

*   **Compute Limitations (DigitalOcean VPS):** Strictly limited to GitHub Student VPS (1-2GB RAM, 1 vCPU). 
    *   *Decision:* We are dropping Temporal.io and Neo4j. We using **SQLite (w/ JSON extensions)** for state/graph emulation and embedded cron/APScheduler for the Chaser.
*   **Hosting Frontends:** Basic Dashboards for employees (built via the `frontend-design` skill) will be hosted on Vercel/Netlify.
*   **LLM Provider:** `moonshotai/kimi-k2-instruct` via **NVIDIA API**.
    *   It fully supports native tool calling (OpenAI-compatible endpoints).
    *   Massive 128,000 token context window.
*   **File Storage:** Direct API sync to **Google Drive** to prevent the tiny VPS SSD from filling up with CAD drawings and videos.
*   **Authentication:** Magic links for employee dashboards. Hardcoded JSON mapping for WhatsApp Number -> Employee Role.

---

## 5. DIRECTIVES FOR THE NEW AI AGENT

**The User's Sentiment:** 
> *"Look honestly I have answered `discovery.md` to my best ability but I feel like your questions are not enough. lets create a context.md file where you transfer all your context along with a prompt to see the current discovery.md rework it and explain it everything you know for a higher quality result, I am migrating to a different model and your task is to ensure that process is very smooth."*

**Your Immediate Action Items:**
1. **Acknowledge & Validate:** Confirm you have read this `context.md` file AND the files listed in Section 1.
2. **Critique the Original Discovery:** The previous `discovery.md` was too shallow (only 5 broad sections). Point out its flaws. What did it miss regarding webhook retries? Database race conditions in SQLite? Auth token refresh for Google Drive?
3. **Generate a Deep-Dive Discovery Questionnaire:** Act as a Principal Systems Architect. Hit the user with advanced, edge-case probing questions. We need undeniable clarity before locking in the final `PRD.md` and `architecture.md`. Focus heavily on failure modes, error recovery, API latency handling, and context buffering logic.