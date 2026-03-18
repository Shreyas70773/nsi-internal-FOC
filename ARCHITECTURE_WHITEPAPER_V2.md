# System Architecture & Orchestration Spec V2

Based on the hierarchical multi-agent structure diagram, this document defines the exact technical orchestration for the WhatsApp-native business automation system. It specifically addresses pain points like multi-document sessions, asynchronous automated follow-ups ("chasing"), and high-level analytics.

---

## 1. COMMUNICATION GATEWAY LAYER

### A. The WhatsApp Primary Ingress & Egress
* **Constraint Addressed:** WhatsApp handles messages discretely (1 message = 1 webhook event). Users cannot easily upload 3 PDFs in a single atomic bundle with text without it breaking into multiple events.
* **Mechanism:** 
  * The integration acts as the primary sensory organ. It feeds the **Router Agent**.
  * **Session Buffering ("The Shopping Cart"):** For tasks like "Compare these 3 PDFs", the Router Agent maintains a temporary state buffer (cached in the Data Store with a timeout, e.g., 10 minutes). 
    * *Example:* If a user says "Compare the incoming quotes," the Router opens a `Wait_State`. The user uploads PDF 1, PDF 2, PDF 3. Once the user says "Done" or the timeout hits, the Router bundles all 3 files and passes the array to the relevant *Supervisor Agent*.

### B. The Email / Escalation Agent
* **Role:** Operates in parallel to WhatsApp. Used strictly when tasks require formal asynchronous tracking, heavy attachments, or when a user is unresponsive to WhatsApp pings.

---

## 2. TRIAGE & ROUTING LAYER (The Brain Stem)

### A. The Master Router Agent
* Sits directly behind the gateway. 
* **Rules of Engagement:**
  1. Does this message contain a direct command? Route to **Supervisor Agents**.
  2. Is this message a status update ("I finished the drawing")? Route to **CONTROL PANEL Receiver Agent**.
  3. Is this a casual conversation? Store in Graph RAG, do not trigger heavy compute.

---

## 3. EXECUTION TIER (Hierarchical Agents)

### A. Supervisor Agents (Domain Experts)
Based on your diagram, domains are split. Examples:
* **Procurement Supervisor:** Handles pricing, vendor quotes, and component buying.
* **Engineering/Project Supervisor:** Manages CAD drawings, technical specs (e.g., 19m tanks), and interconnecting nozzle verifications.
* **Finance/Admin Supervisor:** Handles invoices, MOA, bank documentation.

### B. Sub-Agents (Specialized Workers)
The Supervisors break tasks down and assign them to Sub-Agents.
* *Example:* The Procurement Supervisor needs to compare 3 vendor quotes.
  * Sub-Agent 1 (using `pdf` skill) extracts text/tables from Quote A.
  * Sub-Agent 2 (using `pdf` skill) extracts text/tables from Quote B.
  * Sub-Agent 3 (using `docx` skill) writes the "Comparison Matrix.docx".

### C. The Shared Tooling Layer (MCP + SKILLS + CUSTOM FUNCTIONS)
All Sub-Agents interface directly with the local repository `skills-main/skills`. This prevents prompt bloat; the agents don't need to know *how* to make a DOCX, they just trigger the `docx` skill via Model Context Protocol (MCP).

---

## 4. STATE, MEMORY & CONTROL PANEL (The Nervous System)

### A. Control Panel Receiver Agent
* Intercepts updates from the Router and signals from Sub-Agents when tasks are generated or completed. 

### B. The "Chaser" Engine (Task state & Follow-ups)
* **Goal:** Stay on a team member's neck until a task is done.
* **Implementation:**
  * When a Supervisor assigns a task (e.g., "Govind, get tunnel washer video"), the Control Panel logs this in the **Data Store** under the `Employee Task List`.
  * **The Tick/Cron Loop:** An asynchronous background worker checks the database every X hours. 
  * **Escalation Protocol:**
    1. *T+12 Hours:* Trigger WhatsApp Agent: "Hey Govind, any update on the washer video?"
    2. *T+24 Hours:* Trigger WhatsApp Agent: "Govind, still waiting on the video for the client."
    3. *T+48 Hours:* Trigger Email Agent: Sends formal email to Govind, CC'ing 'Dad Africa' reporting the blockage.

### C. Data Store & Big File Storage
* **Metadata & Relationships:** Neo4j or similar Graph RAG. Tracks relationships (e.g., *Imran* -> *Fine Techno Pack* -> *3 Million L Tank* -> *Invoice.pdf*).
* **Binaries:** Google Drive API. Ensures the local server isn't bloated. The DB holds the GDrive URL strings.

---

## 5. ANALYTICS & INSIGHTS MODULE (The Eye in the Sky)

### Admin/Overview Router
* Sits beside the control panel and constantly aggregates the velocity of tasks across the `Employee Task Lists`.

### Deliverables
* Utilizing the `web-artifacts-builder` or `frontend-design` skills, this module can dynamically generate internal React/HTML dashboards showing:
  * Total pending tasks per employee.
  * Bottlenecks (e.g., "Imran is taking average 4 days to supply updated Autocad drawings").
  * Outstanding payments vs. Received quotes.
* Alternatively, utilizing the `xlsx` skill, it generates an automated "Daily EOD Report" spreadsheet and drops it into the WhatsApp Main Group every day at 6:00 PM.

---

## SUMMARY OF ORCHESTRATION UPGRADES

Your diagram works perfectly. To make it a **one-time, bulletproof solution**, the orchestration must enforce:
1. **The Context Buffer:** So multi-file drops on WhatsApp are bundled into a single "job" before processing.
2. **The Background Cron/Tick loop:** LLMs only run when prompted. To "chase" people, a traditional CRON job must pulse the system, prompting the Control Panel to evaluate deadlines and trigger proactive messages.
3. **Skill Segregation:** The agents remain lightweight logic engines; all heavy lifting is pushed down to the `MCP + Skills` layer.