# System Design & Context Engineering Specification

This document solidifies the architectural principles, state management, context engineering, and fault tolerance for the Agentic Workspace Automation System. It upgrades the previous architecture into an enterprise-grade, highly available microservices model.

---

## 1. SYSTEM DESIGN PRINCIPLES & ARCHITECTURE

The system follows an **Event-Driven, Hierarchical Multi-Agent System (HMAS)** pattern, designed to handle asynchronous communication, scale horizontally, and gracefully recover from failures.

### Core Stack Recommendations:
* **Message Broker / Router:** Kafka or Redis Pub/Sub (handles the asynchronous nature of WhatsApp webhooks).
* **State Machine (The Chaser):** Temporal.io or AWS Step Functions (guarantees tasks stay alive and timers don't die if the server restarts).
* **Active Memory (Context Buffer):** Redis (fast read/write for ongoing conversations).
* **Long-Term Knowledge Storage:** Neo4j (GraphDB) + Vector Database (pgvector / Qdrant) for Entity linking and RAG.
* **Integrations standard:** Model Context Protocol (MCP) using the `mcp-builder` skill.

---

## 2. CONTEXT ENGINEERING (The Memory Pipeline)

To prevent LLM context-window overflow and maintain "hyper-awareness" across daily unstructured conversations, we implement a strict 3-Tier Context Pipeline:

### Tier 1: Active Window (The "Living Room")
* **Mechanism:** Backed by Redis. Stores the last ~20 messages or exact current session (e.g., uploading 3 PDFs).
* **Rule:** Fast, high-context, heavily localized.

### Tier 2: Rolling State Condenser (The "Secretary")
* **Mechanism:** Triggered by an `End_Of_Conversation` timeout (e.g., 30 minutes of silence) or explicit closure ("thanks").
* **Action:** The Context Subagent reads the Active Window, extracts facts (Prices, Tasks assigned, Deadlines, file pointers), and writes these into the database (Graph + Tasks). 
* **Compression:** It replaces the 20 messages with a 1-paragraph summary block and clears the Redis cache.

### Tier 3: Graph RAG (The "Library")
* **Mechanism:** When a user asks "What was that quote Imran sent last week?", the Agent uses Graph RAG. It pulls the Node `Vendor: Imran` → Edge `Sent Quote` → Node `Quote_Pricing_Data`, dynamically injecting only the necessary context into the prompt, rather than searching raw chat logs.

---

## 3. THE "CHASER" STATE MACHINE (Persistent Follow-ups)

Using an orchestration engine like **Temporal.io** guarantees that follow-ups (chases) survive server crashes and API rate limits. 

**The Chaser Workflow:**
1. **Task Injection:** Subagent detects "Govind needs to send washing machine video by tomorrow." Task is created in the DB with `Assignee: Govind`, `Deadline: T+24h`, `State: Pending`.
2. **Phase 1 (The Light Nudge):** At T-4h from deadline, system routes WhatsApp message: *"Hi Govind, just a reminder about the washing machine video required today."*
3. **Phase 2 (The Firm Chase):** At Deadline+2h: *"Govind, the washer video is overdue. Are there any blockers I can help with?"*
4. **Phase 3 (Escalation & Platform Shift):** At Deadline+12h: The State Machine triggers the **Email Integration**. Sends a formal email to Govind, CCing the Manager (Dad Africa) marking the objective as `Blocked`.
5. **Resolution:** If Govind replies to the bot with "Here is the video", the Task Agent intercepts, updates the State Machine to `Complete`, halts the timers, and stores the video in Drive.

---

## 4. INDIVIDUAL EMPLOYEE DASHBOARDS

The system generates decentralized, continuously updated Web UIs for team members, built using the `frontend-design` & `web-artifacts-builder` skills.

### Architecture:
* **The Interface:** A lightweight Next.js / React Web App.
* **Authentication:** Magic links sent daily via WhatsApp (e.g., "Good morning Govind, here is your agenda for today: `https://internal.pacific/govind/secure-token`").
* **Capabilities per Dashboard:**
  * **Urgency Matrix:** Tasks sorted by standard, overdue, and "Manager Escalated".
  * **Upload Portal:** Allows them to upload heavy files (CAD drawings, large videos) directly to the system without WhatsApp's 16MB/64MB media limits.
  * **Agent Chat:** A private 1-on-1 chat window specifically pre-loaded with *their* active tasks to talk to the Subagent and ask for help formatting their work.

---

## 5. THIRD-PARTY INTEGRATIONS VIA MCP

Instead of hardcoding APIs into the main prompt, the system relies on isolated Model Context Protocol (MCP) servers.

* **CRM/ERP Integration:** An MCP server exposes tools like `get_client_record` or `update_sap_inventory`. The Agent simply calls these tools.
* **Drive/Storage:** GDrive/OneDrive MCP server handles `upload_file` and `get_share_link`.
* **Outbound Comms:** `send_email` or `send_slack` tools exposed to the internal Router.
* *Advantage:* If you change ERP systems in 2 years, you only swap the single MCP server; the Agent's brain and routing logic remain untouched.

---

## 6. EDGE CASES & FAULT TOLERANCE

A robust system must anticipate failure. The design enforces the following fallbacks:

* **Edge Case 1: The "Junk Drop" (Spam/Unrelated Chat)**
  * *Risk:* Group members discussing personal matters costs API tokens and pollutes the DB.
  * *Solution:* Ingress Router has a lightweight, local, fast-classification model (e.g., Llama 3 8B or small BERT) that scores "Business Intent". If Intent < 0.8, it ignores the chat entirely.

* **Edge Case 2: WhatsApp API Rate Limits / Bans**
  * *Risk:* If the Chaser bot sends too many follow-ups, Meta blocks the number.
  * *Solution:* Throttle queues. Implemented an exponential backoff matrix. If WhatsApp throws a 429 Error, the system auto-shifts communications to the Email Subagent.

* **Edge Case 3: Conflicting PDF/Data Extraction**
  * *Risk:* User uploads two PDFs with conflicting prices for the same part.
  * *Solution:* The Data Indexer detects a price collision in the Graph DB. It immediately pauses and throws a "Discrepancy Exception" back to the human on WhatsApp: *"You uploaded a quote for Zincalume at ₹1137, but yesterday's quote was ₹1000. Which is the single source of truth?"*

* **Edge Case 4: Context Window Exhaustion**
  * *Risk:* User asks "Summarize the entire month's operations".
  * *Solution:* Vector DB enforces `Max_Tokens`. The system utilizes a Map-Reduce agentic strategy (breaking the month into weeks, summarizing weeks individually, then merging summaries) rather than loading 30 days of raw logs into the prompt.