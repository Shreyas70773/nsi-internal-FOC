To acknowledge you are ready, reply with:
**"ANALYZER ONLINE: Waiting for chat logs. I will map all human workflows into strict Sub-Agent orchestration designs aligned with your Engineering Specs."**

ANALYZER ONLINE: Waiting for chat logs. I will map all human workflows into strict Sub-Agent orchestration designs aligned with your Engineering Specs.

Based on the chat exports in your workspace (specifically I have an idea.md and PROJECT_ANALYSIS_CLEAN.md), I have identified several manual operational workflows. Here are the proposed Sub-Service designs:

⚙️ Function Discovered: Automated Procurement & Sourcing Tabulation
A. Business Justification:
The team (Shibu, Govind) frequently pastes raw vendor offers, technical specs (e.g., "SS 316L COIL - 2B FINISH"), and pricing directly into the WhatsApp group. Shreyas is currently manually creating and linking external Google Sheets to track this ("Supplier Outreach Management Sheet"). This process is ripe for automated extraction and tabulation.

B. Event Trigger & Ingress:
The Router's Context Buffer triggers when it detects messages containing material dimensions, pricing schemas, vendor contact details, or PDF attachments resembling vendor quotes (e.g., "MAGIZHINI ENTERPRISES OFFER").

C. Assigned Supervisor / Sub-Agent:
Procurement Supervisor Agent:
System Prompt: "You are the Procurement Analytics Agent. Extract vendor names, material specifications, quantities, and pricing from conversational text or uploaded PDFs. Append this structured data directly to the active sourcing tracker."

D. Skill & MCP Tooling Required:

pdf: To parse incoming vendor quotation sheets.
xlsx: To automatically tabulate and update the "Supplier Outreach Management" spreadsheet without human intervention.
E. Graph RAG & Memory Action:
Node(Vendor) -> Edge(Provided_Quote_For) -> Node(Material/Equipment) -> Edge(Priced_At) -> Node(Value)

F. The Chaser / Escalation Protocol:
If a team member shares a vendor contact but no pricing is uploaded within 24 hours, the Temporal.io state machine pings the chat: "Checking in—did we receive the quote from [Vendor Name] yet?"

⚙️ Function Discovered: Boilerplate Document Generation (PO & Invoicing)
A. Business Justification:
The chat explicitly mentions the need to "make performa invoice, make commerical qoutation, put spesific company letter head." Additionally, Shreyas manually drafts payment terms and shares Word document links for approval ("clauses-payment-terms.pdf... If these terms are okay we will add to PO").

B. Event Trigger & Ingress:
Keyword invocation triggered by phrases such as "Draft PO for...", "Generate Proforma for...", or simply providing a list of line items and saying "Put this on a letterhead."

C. Assigned Supervisor / Sub-Agent:
Contract & Finance Sub-Agent:
System Prompt: "You are the Financial Document Agent. Take raw conversational line items, pricing, and negotiated terms, and generate strictly formatted PDF/Word documents using the Pacific Unity MEA letterhead templates."
D. Skill & MCP Tooling Required:

docx: For rendering the formal, styled Purchase Orders or Invoices using pre-approved templates from the templates/ directory.
pdf: To convert the final .docx to an immutable format before sending it back into the WhatsApp chat.
E. Graph RAG & Memory Action:
Node(Company/Client) -> Edge(Issued_Document) -> Node(Proforma/PO_ID) -> Edge(Contains_Terms) -> Node(Payment_Clauses)

F. The Chaser / Escalation Protocol:
Once the bot drops the drafted document back into WhatsApp, a Temporal timer starts. If the decision-maker (Dad Africa) does not reply with "Approved" or "Changes required" within 4 hours, the bot nudges: "Pending approval on the PO for [Vendor]. Reply 'y' to finalize."

⚙️ Function Discovered: Task Extraction & Follow-up Engine
A. Business Justification:
Tasks are handed out conversationally (e.g., "@Shreyas Sunil check the upcoming requirements", "Pls pay 25 K to Shahid", "Prepare a email id for Pacific unity"). Currently, completion is loosely tracked by employees texting back "Done" or "Paid".

B. Event Trigger & Ingress:
The Context Buffer evaluates messages with explicit directives ("Pls pay", "Prepare", "Call mutashi") or @ mentions combined with action verbs.

C. Assigned Supervisor / Sub-Agent:
Operations/Admin Supervisor:
System Prompt: "You are the Operations Tracking Agent. Identify explicit task assignments between team members in the chat. Record the Assigner, the Assignee, and the core objective. Maintain a pending state until explicit confirmation of completion is detected."

D. Skill & MCP Tooling Required:

mcp-builder: Connect to an external Ticket/Task tracking system (like Jira, Trello, or a simple internal database) to formally log the extracted tasks.
E. Graph RAG & Memory Action:
Node(Dad Africa) -> Edge(Assigned_Task_To) -> Node(Govind/Shreyas) -> Edge(Task_Context) -> Node(Action)

F. The Chaser / Escalation Protocol:
Temporal SLAs are applied based on task urgency. For financial tasks ("Pay 25k"), the Chaser pings the assignee after 2 hours. For administrative tasks ("Buy domain"), it pings at 9:00 AM the following morning. If unacknowledged after 3 automated WhatsApp nudges, it escalates by emailing both the Assignee and Assigner outlining the pending blocker.

I completely understand. Because you are deploying this on the DigitalOcean GitHub Student VPS (which usually means very strict constraints like 1GB or 2GB of RAM and maybe 25GB of SSD), a setup with heavy databases (like full Neo4j) or heavy task engines (like Temporal) would literally crash the server before it even booted.

We must adjust the system to be hyper-efficient, monolithic, and lightweight, while offloading the heavy lifting (storage to GDrive, compute to NVIDIA's KIMI K2).

I have created two new files mapping to your framework:

discovery.md - This is your structured scoping questionnaire. It specifically asks you how to handle the DigitalOcean constraints (e.g., using SQLite instead of Neo4j), how you'll manage Google Drive authentication (OAuth vs Service Accounts), what the context limit is for KIMI K2 via NVIDIA, and how we map employee numbers for the tracking engine.
architecture.md (Draft V1) - An incredibly optimized technical system design. I stripped out the heavy software and replaced it with a VPS-friendly equivalent:
Database: SQLite (takes zero RAM when idle).
The Chaser/Nag System: Using an embedded thread scheduler (APScheduler or node Cron) instead of Temporal.
File Storage: Automated sync-and-delete. (Downloads the PDF from WhatsApp, pushes to Google Drive, saves the Drive Link to SQLite, then deletes it locally to save your 25GB disk space).
Frontend: Static Pre-compiled JS instead of a full SSR Next.js server to give employees their dashboards.
Please review the questions in discovery.md when you have time. Once you provide the answers (even rough ones), we can generate the final PRD.md and lock in the Architecture so the build can commence!

    