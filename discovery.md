# PROJECT DISCOVERY & SCOPING QUESTIONNAIRE

**Objective:** This document serves as Phase 1 of our product development framework. Your answers to these questions will dictate the final Product Requirements Document (PRD) and solidify the exact Architecture before any code is written.

Please review the sections below and provide your answers/decisions.

---

## 1. INFRASTRUCTURE & COMPUTE CONSTRAINTS
*Context: You are using a DigitalOcean VPS (GitHub Student Tier), which typically provides 1GB - 2GB RAM and 1 vCPU. This restricts heavy platforms like Kafka, full Neo4j, or large Java-based Temporal instances.*

* **Q1.1:** Given the 1-2GB RAM constraint, are you okay with downgrading our heavy stack (Temporal, Neo4j, Redis) to lightweight alternatives? (e.g., using **SQLite** for relational/vector data, and **APScheduler/Celery/Cron** in Python for the "Chaser" state machine?)

yeah I am okay as long as the end outcome and result is the same
* **Q1.2:** Will we deploy this as a single monolithic Docker/Docker-Compose file to maximize resources on the VPS?
I am not quite sure

* **Q1.3:** Do you have a domain name purchased (e.g., `pacificunity.ae`) so we can route OpenClaw webhooks over secure HTTPS to the VPS?

I have a few domains, we can host on vercell or netlify and think from there 
---

## 2. LLM LOGIC & NVIDIA API (KIMI K2)
*Context: We are routing intelligence through NVIDIA's API using the KIMI K2 model.*

* **Q2.1:** Does KIMI K2 via the NVIDIA API support native "Function Calling" / "Tool Calling"? (If not, we will need to build a custom ReAct/JSON regex prompt parser for it to use the `skills`).

**Yes, KIMI K2 via the NVIDIA API supports native function calling (also known as tool calling).** [github](https://github.com/MoonshotAI/kimi-cli/issues/811)

## Key Evidence
NVIDIA's official model card for moonshotai/kimi-k2-instruct explicitly states it has "strong tool-calling capabilities," where users pass a list of tools in OpenAI-compatible format, and the model autonomously decides when to invoke them. 

## Usage Details
It uses standard OpenAI API structure with `tools` and `tool_choice="auto"` parameters, supporting multi-turn interactions with tool results fed back as `role: "tool"` messages, as shown in NVIDIA's end-to-end weather tool example. [build.nvidia](https://build.nvidia.com/moonshotai/kimi-k2-instruct/modelcard)

No custom ReAct/JSON regex parser is needed, since the NVIDIA NIM inference engine handles native tool parsing for this model.

* **Q2.2:** What is the specific context window limit for the KIMI K2 endpoints you have access to? (This will determine how aggressively our Context Buffer needs to summarize).
The KIMI K2 endpoints on NVIDIA API, specifically the moonshotai/kimi-k2-instruct model, have a context window limit of 128,000 tokens.


* **Q2.3:** Do we have fallback keys (e.g., Anthropic/OpenAI) if the NVIDIA endpoint rate-limits us during heavy data extraction (like OCR on large PDFs)?
yeah I have openAI we can set up anthropic as well 
---

## 3. GOOGLE DRIVE STORAGE INTEGRATION
*Context: To save local VPS disk space, we are offloading large CAD drawings, videos, and PDFs directly to Google Drive.*

* **Q3.1:** Will you be using a **Google Service Account** (a bot email that owns its own isolated Drive) or **OAuth** (where the system logs in as *you* and reads/writes to a specific folder in your personal/company Drive)?
Whichever is more suitable for this usecase 
* **Q3.2:** What should the exact folder hierarchy look like in Google Drive? (e.g., `WhatsApp_Bot / [Client_Name] / [Project_Name] / Invoices`)
yeah that works 
---

## 4. TEAM IDENTIFICATION & THE "CHASER"
*Context: The system needs to track who hasn't replied and escalate.*

* **Q4.1:** How will we map WhatsApp phone numbers to Employees? Will we have a hardcoded JSON/SQLite map (e.g., `+971 55 ...` = `Govind`), or should the bot "learn" and ask new numbers who they are? lets hardcode it initially

* **Q4.2:** What is the standard business hour timezone for the "Chaser" timers? (e.g., Do we stop chasing after 6:00 PM GST and resume at 9:00 AM GST, or run 24/7?)
we run 24/7 NO Time zone because some members are in Africa While some are in India

* **Q4.3:** For the formal email escalations, do we have a dedicated SMTP server/email address (e.g., `bot@pacificunity.com`) to send from?

We own info@stelastra.com and its on outlook we will mostly send through that

---

## 5. DASHBOARDS & FRONTEND
*Context: Employees will receive links to see their tasks.*

* **Q5.1:** Do these employee dashboards need to be accessible to the public internet, or will you restrict them behind a basic password/Magic Link?
lets keep it accessible to internet but not allow crawllers

* **Q5.2:** Considering VPS constraints, are you comfortable serving a very lightweight, pre-compiled static HTML/JS dashboard from the Python/Node backend instead of a heavy Next.js frontend?
yeah I am okay as long as it works 

---
*Once these questions are answered, the PRD.md will be generated to lock in the features, followed by a finalized `architecture.md` update.*