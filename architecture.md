# ARCHITECTURE SPECIFICATION (Draft V1)
*Note: This architecture is optimized specifically for a lightweight environment (DigitalOcean GitHub Student VPS: 1-2GB RAM, 1 vCPU) utilizing NVIDIA's KIMI K2 via API and Google Drive for binary storage.*

---

## 1. HIGH-LEVEL TOPOLOGY (Asset & Request Flow)

1. **Ingress (OpenClaw Tunnel):** Receives WhatsApp Webhooks `(JSON via HTTPS POST)`.
2. **Web Server (FastAPI / Express):** Lightweight layer exposed to the internet. Converts Webhook -> Internal Event.
3. **Orchestrator Layer (Chaser & Context):** Parses intent.
4. **Intelligence Layer:** Calls NVIDIA API (`KIMI K2`) to decide what tool to use.
5. **Execution Layer (Skills):** Modifies an XLSX, creates a DOCX, or uploads a PDF to Google Drive.
6. **Egress (OpenClaw API):** Sends the response/PDF back to the WhatsApp chat.

---

## 2. INFRASTRUCTURE & TECH STACK (VPS Optimized)

Due to the strict memory limits of a basic DigitalOcean VPS, we must discard heavy enterprise tools (Kafka, Temporal.io, Neo4j, Next.js) and replace them with single-binary or highly efficient equivalents.

| Component | Enterprise Version (Previous) | VPS Optimized Version (Current) | Justification |
| :--- | :--- | :--- | :--- |
| **Database/Graph** | Neo4j + Redis | **SQLite (w/ JSON extensions)** | Zero RAM overhead. Stores relationships in optimized relational tables. |
| **Task Chaser** | Temporal.io Workflow | **APScheduler (Python) / Node Cron** | Runs inside the main application thread. No separate Java/Go pods required. |
| **State Buffer** | Redis Cluster | **In-Memory Cache + SQLite** | Prevents RAM overflow. Clears after 30 mins. |
| **File Storage** | AWS S3 | **Google Drive API** | Zero hard drive cost. Uses Service Account to sync. |
| **Frontend UI** | Next.js Server (SSR) | **FastAPI Jinja2 / Static React** | Served from the same backend. No NodeJS daemon required. |
| **LLM Inference** | Claude 3.5 Sonnet | **NVIDIA KIMI K2 API** | Hosted remotely. Zero local GPU/VRAM needed. |

---

## 3. CORE SUB-SYSTEMS

### A. The SQLite "Graph" Emulator
Since we can't run Neo4j, we will mimic Graph-RAG using SQLite tables dynamically joined by the Agent:
* `table_entities` (ID, Type (Vendor/Employee/Company), Name)
* `table_documents` (ID, GDrive_URL, Extracted_Summary)
* `table_relationships` (Source_ID, Target_ID, Relation_Type "Quoted_For")

### B. The Google Drive Data Sync
To manage the "Librarian" subagent:
1. Agent receives `Stel_Astra_Specs.pdf` in base64/binary via OpenClaw.
2. App temporarily writes file to `/tmp/drive_sync/`.
3. Calls Google Drive API -> Uploads to `Drive/PacificUnity/Specs/`.
4. Retrieves `webViewLink`.
5. Logs `webViewLink` into SQLite. 
6. Deletes local `/tmp/` file to prevent the 25GB VPS SSD from filling up.

### C. Context Aggregation for KIMI K2
To ensure KIMI K2 doesn't hallucinate or error out:
* Every 5 messages, the system triggers a lightweight prompt to KIMI: *"Condense these 5 lines into a 1-sentence fact log."*
* The fact log is saved to the SQLite conversation history.
* When executing a complex task (e.g., generate Proforma), the app queries the DB for the Fact Log + Active 10 messages -> Formats into a strict JSON payload -> Sends to NVIDIA endpoint.

### D. The "Chaser" Cron Loop
* A threaded background timer wakes up every **1 hour**.
* Queries SQLite: `SELECT * FROM internal_tasks WHERE status = 'PENDING' AND deadline < NOW()`
* For each result, parses the assigned employee's WhatsApp number, generates a strict nudge string via KIMI K2, and pushes the payload to OpenClaw to send the WhatsApp message.

---

## 4. DEPLOYMENT PIPELINE

1. Developer commits code to GitHub.
2. Server pulls via `git pull`.
3. Runs `docker-compose up --build -d`.
   - **Container 1:** Application App (Python/Node) + SQLite Volume + Embedded Cron. (Requires ~300MB RAM)
   - **Container 2:** Caddy/Nginx (Reverse Proxy) for HTTPS SSL Termination. (Requires ~50MB RAM)
   - *Total VPS RAM Footprint: < 500MB.*

*Next Steps: Update this architecture doc after PRD generation once discovery questions are answered.*