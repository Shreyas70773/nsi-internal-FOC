# WhatsApp Bot Integration & Subagent Orchestration Spec

## 1. Context & Use Case Definition

This document serves as the foundational design logic for the Analysis Model to orchestrate a WhatsApp-native business automation bot acting as a tunnel via OpenClaw. 

**Core Input Formats (The "Shabby" Data)**
The system must be built assuming all input arrives in raw, concatenated WhatsApp message histories. The model should *not* expect clean structured data right away. Real-world inputs will look like this:
```text
[16:40, 16/03/2026] Shreyas Sunil: I got from urja itself
[11:17, 15/01/2026] Shreyas Sunil: Not going to use this but it's good
[15:15, 16/01/2026] Dad Africa: Initial documents required...
<attachment: .pdf, .docx, .jpeg>
```

**Core Deliverables:**
- Interpret chaotic conversation threads across Personal, Main Group, Side Group, and Project Group chats.
- Automatically digest attached payloads (PDF, DOCX, XLSX, JPEG, PNG).
- Produce specialized business artifacts (Proforma Invoices, Commercial Quotations, letterheads).
- Follow up on tasks and assign team action items.
- Sort and file documents automatically into a folder hierarchy.
- Maintain a sequence/graph network of uploaded assets and references to easily fetch requested docs.

---

## 2. Existing Skill Toolset Mapping

The following existing skills (located in `skills-main/skills`) are immediately relevant to this orchestration and must be heavily utilized by the corresponding subagents:

1. **`docx`**: Crucial for generating Proforma Invoices, Commercial Quotations, and applying company letterheads based on the raw project requirements discussed in the chat.
2. **`xlsx`**: For extracting requirement tables from Excel uploads or parsing the "Supplier Outreach Management Sheet".
3. **`pdf`**: For processing inbound vendor quotes (e.g., `MAGIZHINI ENTERPRISES OFFER.pdf`) and combining output documents.
4. **`claude-api`** & **`mcp-builder`**: To handle the OpenClaw tunnel integrations, enabling the bot to route webhooks or API requests from WhatsApp into subagent workflows.
5. **`brand-guidelines` / `theme-factory`**: To strictly adhere to the `Pacific Unity MEA FZ-LLC` brand standards and letterheads when generating output artifacts.

---

## 3. Subagent Orchestration Architecture

To properly digest the chaotic multi-threaded chat input and execute tasks, the system must coordinate multiple subagents. The Analysis Model should orchestrate them as follows:

### A. The Ingress Parsing Subagent (The "Ear")
* **Role**: Sits immediately behind the OpenClaw tunnel. 
* **Action**: Receives raw string text `[HH:MM, DD/MM/YYYY] Name: MSG`. 
* **Output**: Transforms continuous text blogs into structured chronological `JSON` arrays containing `Speaker`, `Timestamp`, `Intent_Flags`, and `Attachment_References`. Reconstructs multi-line messages that break typical regex parsers.

### B. The File & Graph Indexer Subagent (The "Librarian")
* **Role**: Operates whenever the Ingress subagent detects a file payload (PDF, DOCX, JPEG, etc.).
* **Action**: 
  1. Trigger Vision or `pdf`/`xlsx` skills to extract the file metadata and core contents.
  2. Dynamically categorize and save the file into standardized company folders (`Storage Tanks/`, `Logistics/`, `Invoices/`).
  3. Map the entity and create a connection in a Graph Network (e.g., Link `1500KL Technical spec.pdf` to the entity `Imran Tank`).

### C. The Task & Follow-up Subagent (The "Manager")
* **Role**: Scans parsed JSON conversational nodes for action items ("check upcoming requirements", "Pls pay 25 K to Shahid", "Prepare a email id").
* **Action**: Creates stateful tasks, logs the assignee, lists dependencies, and subsequently drafts reminder WhatsApp messages to be routed back through OpenClaw.

### D. The Commercial Generation Subagent (The "Clerk")
* **Role**: Invoked when an intent requires documentation creation (e.g., "Make performa invoice for 3M liter tank").
* **Action**: 
  1. Utilizes the **Graph Indexer** to retrieve the correct pricing variables and vendor details.
  2. Uses the **`docx`** skill to draft the Proforma Invoice.
  3. Uses **`pdf`** skill to lock the invoice and routes it back via OpenClaw to the WhatsApp chat.

---

## 4. Mini-Functions & Projects for Development

To make this orchestration successful, the Analysis Model should initiate the creation of the following distinct modules/functions:

#### Mini-Project 1: `whatsapp-parser-utility`
Create an intelligent Regex-based and LLM-assisted parser that correctly resolves line-breaks, missing timestamps, threaded replies, and forward indicators in WhatsApp text dumps.

#### Mini-Project 2: `doc-graph-network`
A standardized graph state schema that maps `Chat Thread` ↔ `Mentioned Entity` ↔ `Locally Stored File`. Needs a query function to answer WhatsApp queries like "Fetch the latest drawing for the 19m tank."

#### Mini-Project 3: `artifact-templating-engine`
A suite of JavaScript/Python scripts leveraging the `docx-js` (referenced in `skill.md`) to create 3 parameterized templates:
- Template A: Commercial Quotation 
- Template B: Proforma Invoice
- Template C: Formal Company Letterhead Doc

#### Mini-Project 4: `openclaw-router-mcp`
Implement an MCP (Model Context Protocol) server utilizing the `mcp-builder` skill. This MCP server will expose the capabilities of the subagents to the bot interface, allowing the bot to dynamically call upon `FetchDocument()`, `GenerateInvoice()`, or `AssignTask()` when specific trigger words are intercepted in the chat.

---

## 5. Next Steps for the Analysis Model

When interpreting new, chaotic conversation histories:
1. **Never attempt to just summarize it**. Instead, pass it through the *logical equivalent* of the **Ingress Parsing Subagent**.
2. Identify missing tooling gaps: Do we need a new skill for scraping specific images? (If so, use `skill-creator`).
3. Formulate the technical JSON or structural outputs first before acting on any documented requirement.