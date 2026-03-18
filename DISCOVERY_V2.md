# DEEP-DIVE DISCOVERY QUESTIONNAIRE V2
## Principal Systems Architect Review

**Purpose:** This document replaces the original shallow `discovery.md`. It probes every failure mode, race condition, security gap, and operational edge case that must be resolved before generating the final `PRD.md` and locking the architecture. Answer as many as you can -- even "I don't know, you decide" is a valid answer that lets us make an informed default.

**How to answer:** Write your response directly below each question. One line is fine. If a question doesn't apply, write "N/A".

---

## SECTION 1: THE OPENCLAW TUNNEL (The Front Door)

*The entire system lives or dies by this integration. We need absolute clarity on its behavior.*

**Q1.1 — Webhook Contract:** What exact HTTP method and payload format does OpenClaw deliver? Is it a `POST` with a JSON body containing `{ from, message, media_url, timestamp }`? Or does it wrap the WhatsApp Cloud API format verbatim? We need to know the exact schema to build the Ingress Parser.
OpenClaw’s WhatsApp‑style webhook contract is not a raw copy of the WhatsApp Cloud API; instead it exposes its own normalized schema over a POST with a JSON body.

HTTP method and envelope
HTTP method: POST

Path: typically /api/channels/whatsapp/webhook (or your chosen hooks path, e.g., /hooks/whatsapp).

Content‑type: application/json (or whatever format your mapping expects, but JSON is standard).
​

The payload is not simply { from, message, media_url, timestamp }; it reflects the WhatsApp Cloud API object structure, but then mapped into OpenClaw’s internal message:received‑style context (see below).

Actual payload schema (for Ingress Parser)
For WhatsApp inbound messages, the initial webhook payload is the WhatsApp Cloud API format something like:

json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "string",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": { "display_phone_number": "12345678900", "phone_number_id": "23456789011" },
            "contacts": [ { "profile": { "name": "John" }, "wa_id": "1234567891" } ],
            "messages": [
              {
                "id": "wamid...",
                "from": "1234567891",
                "timestamp": "1712345678",
                "type": "text"|"image"|"audio"|"audio_context"|"voice"|"video"|"document"|"location"|"contacts"|"interactive"|"sticker"|"unknown",
                "text": { "body": "Hello" },
                "image": { "id": "fid...", "caption": "caption" },
                "audio": { "id": "fid...", "mime_type": "audio/ogg" },
                "video": { "id": "fid...", "caption": "caption" },
                "document": { "id": "fid...", "filename": "file.pdf", "caption": "caption" },
                "location": { "latitude": 12.123, "longitude": 78.901 },
                "contacts": [ ... ],
                "interactive": { ... },
                "sticker": { ... }
              }
            ]
          }
        }
      ]
    }
  ]
}
OpenClaw then transforms this into its own internal message:received context for hooks, which looks like:

ts
{
  type: "message",
  action: "received",
  context: {
    from: string,           // Sender identifier (e.g., phone number)
    content: string,        // Normalized text content
    timestamp?: number,     // Unix timestamp when received
    channelId: "whatsapp",
    accountId?: string,
    conversationId?: string,
    messageId?: string,
    metadata?: {
      to?: string,
      provider?: "whatsapp",
      senderId?: string,
      senderE164?: string,
      raw?: { /* original WhatsApp Cloud API payload */ }
    }
  }
}
For media, the raw field inside metadata typically contains the WhatsApp‑native image, audio, video, document, etc., each with an id and optional caption or filename.

Implications for your Ingress Parser
Use POST with JSON.

Parse the WhatsApp Cloud API envelope first (top‑level object, entry, changes, value.messages).
​
​

Then map it into OpenClaw’s expected message:received‑style fields (or pass the raw payload through a mapping hook that OpenClaw’s hooks.mappings config consumes).




**Q1.2 — Webhook Retry Policy:** If our server returns a 5xx or times out, does OpenClaw retry the delivery? If yes, how many times and at what interval? This determines whether we need idempotency keys (deduplication tokens) on every incoming message to prevent double-processing.

OpenClaw implements a retry policy for outbound webhook deliveries when your server returns 5xx errors or times out.

Retry Details
OpenClaw retries 3 times by default on transient failures like HTTP 5xx (server errors), timeouts (ETIMEDOUT), or connection issues (ECONNRESET).

Interval: Exponential backoff starting at a channel-specific minimum (e.g., 400-500ms for messaging channels like WhatsApp/Telegram), capped at 30 seconds max delay, with 10% jitter to avoid thundering herd.

Total attempts: Initial delivery + 3 retries = up to 4 deliveries per event.

What triggers retry: 5xx responses, timeouts, or provider-indicated retryable errors (e.g., via Retry-After header); 4xx (like 400/401/403) are treated as fatal and not retried.

Idempotency Recommendation
Yes, implement idempotency keys. Use the webhook's messageId (from WhatsApp Cloud API payload) or OpenClaw's conversationId/messageId as a deduplication token. Store processed IDs in Redis/Postgres with a TTL (e.g., 1 hour) to handle retries safely without double-processing.



**Q1.3 — Webhook Timeout:** How many seconds does OpenClaw wait for our `200 OK` before considering the delivery failed? If it's 5 seconds, we CANNOT run LLM inference synchronously in the webhook handler -- we must enqueue and respond immediately.OpenClaw waits 10 seconds for your server to return 200 OK (or other 2xx) before considering the webhook delivery failed and triggering retries.
​

Timeout Implications
This short window confirms you cannot run synchronous LLM inference (which typically takes 2-30+ seconds) in the webhook handler—doing so risks timeouts on every delivery.

Instead:

Acknowledge immediately: Validate signature/idempotency key, return 200 OK within <500ms.

Enqueue asynchronously: Push to Redis/Kafka/queue worker for LLM processing (e.g., BullMQ, Celery).

Configurability: Some OpenClaw setups allow webhook: 10000 (10s default) in config.yaml, but don't rely on overrides—design for the standard 10s limit.
​

This aligns with webhook best practices (5-30s sender timeouts) to prevent queue buildup from slow receivers.


**Q1.4 — Media Handling:** When a user sends a PDF/image on WhatsApp, does OpenClaw give us: (a) a temporary download URL that expires, (b) the raw base64 in the webhook payload, or (c) a permanent media ID we fetch separately? This determines our file download pipeline and timeout handling.
OpenClaw provides (c) a permanent media ID in the WhatsApp webhook payload for PDFs/images, which your system fetches separately from Meta's servers.​
Media Flow Details

When users send media via WhatsApp, the webhook delivers a media ID rather than raw data or a temporary URL. OpenClaw's plugin then downloads the file automatically using that ID and makes it available in the conversation context as a local temp path or templating variable (e.g., {{MediaPath}}).

This avoids base64 bloat in payloads and supports stable retrieval without expiration concerns, though you handle download timeouts via Meta's API limits.
Pipeline Implications

    Download: Use the media ID with WhatsApp Cloud API endpoints for persistent access—no expiry like temp URLs.

    Timeouts: Set generous limits (e.g., 30-60s) since Meta serves files reliably but caps sizes (images ~6MB, docs 100MB post-processing).

    Agent Handling: Files land in temp storage for agents/commands; no direct base64, keeping payloads lean.

**Q1.5 — Outbound Messaging API:** To send messages BACK to WhatsApp (nudges, documents, responses), what does the OpenClaw API look like? Is it a REST `POST` with `{ to, message, media }` ? What are the rate limits? Can we send PDFs/DOCX as attachments?
OpenClaw handles outbound WhatsApp messaging through its internal Gateway WebSocket protocol rather than a simple REST POST endpoint like { to, message, media }.​
Sending Mechanism

Messages are sent via JSON payloads over WebSocket to the Gateway, which manages the WhatsApp socket connection—requiring an active listener for the target account. Agents or skills trigger these sends automatically (e.g., via templating like {{Reply "text"}}), with no direct external REST API exposed for arbitrary programmatic sends.

Group/direct chat routing follows session rules (e.g., session.dmScope), and access controls like dmPolicy: "allowlist" enforce sender restrictions before outbound delivery.
Rate Limits & Attachments

Rate limits align with WhatsApp/Meta Business API tiers (e.g., Tier 1: 80 msgs/24h per unique recipient, scaling up), enforced by the Gateway to prevent bans—no custom OpenClaw-specific limits documented. PDFs/DOCX are supported as attachments via media uploads (converted to WhatsApp document format, up to 100MB), using similar media ID flows as inbound.

**Q1.6 — Message Status Callbacks:** Does OpenClaw report delivery/read receipts back to us? (e.g., "Message delivered", "Message read"). This matters for the Chaser -- if we know a nudge was *read* but not acted on, the escalation logic changes.

OpenClaw does report message status callbacks for WhatsApp delivery and read receipts, forwarding them through its Gateway WebSocket protocol and logging them in the conversation dashboard or CLI status.​
Callback Details

These statuses ("sent", "delivered", "read") mirror WhatsApp Web's native multi-tick system and appear in real-time logs when monitoring via openclaw status or the chat interface, enabling escalation logic based on read-but-unacted nudges.​​

No direct REST webhook for external apps is exposed; instead, integrate via OpenClaw's internal event queue or dashboard polling for chaser workflows.​
Chaser Implications

    Track message_id from outbound sends against incoming status events (e.g., blue ticks trigger escalation).

    Reliable for 1:1 chats; group reads vary by participant privacy settings per WhatsApp norms.

**Q1.7 — Multi-Chat Identity:** The bot will live in 4+ chats (personal, main group, side group, project group). Is it the same WhatsApp number across all? Does OpenClaw differentiate which chat/group a message came from in its webhook payload?
Yes, OpenClaw uses the same WhatsApp number across all chats, including personal DMs, main group, side group, and project group. This setup relies on a single linked WhatsApp account (via Baileys/WhatsApp Web) managed by one Gateway instance, as sharing the number across multiple instances breaks authentication.
Multi-Chat Support

OpenClaw supports multiple chats on that single number through dedicated configurations like channels.whatsapp.groups for allowlisting specific groups and groupPolicy (e.g., "allowlist"). Group messages are processed separately from personal DMs, with isolated sessions keyed as agent:<agentId>:whatsapp:group:<jid>, ensuring no cross-contamination of context or commands.
Webhook Differentiation

OpenClaw's inbound webhook payloads (for gateway or external integrations) distinguish chat origins using fields like from: <groupJid> for groups versus personal JIDs for DMs, plus sender details such as [from: Sender Name (+E164)] in group batches. Logs explicitly show from: <groupJid> entries, and session keys incorporate the JID to route correctly across personal, main group, side group, or project group messages.
**Q1.8 — OpenClaw Uptime & Fallback:** What happens if OpenClaw itself goes down? Do messages queue on their side, or are they permanently lost? Do we need a secondary tunnel provider as a fallback?
If OpenClaw goes down, incoming WhatsApp messages are not queued by OpenClaw and can be permanently lost if the Gateway is offline long enough. WhatsApp delivers messages via its Web socket (Baileys); a crashed or restarted Gateway drops the connection, and without external queuing, new messages arriving during downtime (>15 minutes) fail to persist unless custom MQ is deployed.
Message Handling

OpenClaw lacks built-in persistent queuing for inbound messages by default—memory-buffered queues risk loss on restart, as noted in deployment guides. Outbound messages benefit from optional write-ahead queues with retries to avoid silent drops post-restart, but inbound relies on the live socket.
Fallback Options

A secondary tunnel provider isn't typically needed, as OpenClaw ties to one WhatsApp number per Gateway (multi-instance sharing breaks auth). Instead, harden uptime with systemd auto-restart, static IP, and credential backups; add external webhook queues or MQ (e.g., via Tencent Cloud) for noisy/high-volume traffic to buffer events during outages.
---

## SECTION 2: SQLITE PERSISTENCE LAYER (The Brain's Memory)

*SQLite is the single source of truth for tasks, entities, relationships, conversation history, and the context buffer. It must be bulletproof.*

**Q2.1 — Concurrent Access Strategy:** The webhook handler writes incoming messages. The Chaser cron reads/writes task states. The context condenser writes summaries. All three hit SQLite simultaneously. Are you comfortable with us enforcing WAL (Write-Ahead Logging) mode and a single-writer queue pattern (all writes go through one serialized async queue)?

I think in this type of a usecase we can goahead with whichever is simpler and whatever you recommednd 


**Q2.2 — Database Backup:** If the SQLite file corrupts (power loss, disk full, Docker crash), we lose ALL task states, entity graphs, and conversation history. Are you okay with us running an automated hourly backup that uploads the `.db` file to Google Drive? This adds ~5 seconds of Drive API latency per hour but gives us point-in-time recovery.

yeah please we must do this

**Q2.3 — Database Size Projections:** Over 6 months of operation, how many messages per day do you estimate across all 4 chats? (Rough guess is fine: 50/day? 200/day? 500/day?) This determines when SQLite will need vacuuming or archival to keep query performance under 50ms.

Across 4 we can take 200 per day worst case

**Q2.4 — Schema Migrations:** When we inevitably need to add a new column or table (e.g., adding "priority" to tasks), how should we handle it? Options: (a) Automatic migration on app startup, (b) Manual SQL scripts you run. Recommendation: automatic.

lets go for automatic

**Q2.5 — Encryption at Rest:** The database will contain vendor pricing, payment amounts, employee phone numbers, and task assignments. Do you want SQLCipher (encrypted SQLite) or is the VPS-level disk encryption sufficient?

VPS level disk encryption is sufficient

---

## SECTION 3: LLM INFERENCE (KIMI K2 via NVIDIA API)

*This is the "intelligence" — every routing decision, every document generation, every context condensation goes through this API. Its failure modes directly impact the user experience.*

**Q3.1 — Rate Limits:** What are the exact rate limits on your NVIDIA API key for KIMI K2? (Requests per minute? Tokens per minute? Concurrent requests?) If we don't know, we must build a token bucket rate limiter defensively.
The free NVIDIA API key (from developer.nvidia.com account signup) for Kimi K2 via NVIDIA's NIM/inference API has a confirmed rate limit of 40 requests per minute (RPM).
Key Limits

    Requests per Minute (RPM): 40 RPM across models in the free trial API Catalog; this is the hard cap for prototyping.

    Tokens per Minute (TPM): Not explicitly documented in NVIDIA sources; some third-party integrations note opaque token restrictions or ~64K TPM similar to other free tiers, but treat as unknown.

    Concurrent Requests: No specific limit stated; design for sequential or low concurrency given the RPM cap and potential queuing on overload.

Defensive Rate Limiter

Since TPM and exact concurrency aren't fully specified, implement a token bucket algorithm in your code to stay under 40 RPM safely—e.g., using Python's time module for leaky bucket throttling at ~0.67 requests/second. This prevents 429 errors even if undocumented limits tighten. Monitor response headers like X-RateLimit-Remaining where available.


**Q3.2 — Latency Budget:** What's the acceptable response time for the user on WhatsApp? If someone says "Generate Proforma for 3M tank", is 10 seconds okay? 30 seconds? 2 minutes? This determines whether we respond with "Working on it..." immediately and deliver the document asynchronously, or block until done.

depending on the task complexity, we can say working on it and take how much ever time, also remember we need to be able to check status on whatsapp of the task. 

**Q3.3 — Hallucination Guardrails for Financial Documents:** KIMI K2 will generate Proforma Invoices and Commercial Quotations with real pricing (e.g., ₹1,137/unit sealant, $28,665 USD totals). If the LLM hallucinates a price, the business sends a wrong invoice. What's the safety net? Options: (a) Human-in-the-loop: bot sends a draft to "Dad Africa" for approval before finalizing. (b) Strict template: LLM only fills in variables, never generates prices from memory -- all prices pulled from SQLite. (c) Both. **Recommendation: (c) Both.**
yeah we can try both

**Q3.4 — Fallback Chain:** You mentioned having OpenAI keys and potentially Anthropic. What's the priority order when KIMI K2 fails? Proposed chain: `KIMI K2 → GPT-4o-mini (cheap fallback) → Claude Haiku (emergency)`. Does that work, or do you want to keep it strictly KIMI K2 + one fallback?
yeah that works for initial launch


**Q3.5 — Token Cost Tracking:** Do you want the system to log token usage per request so you can monitor monthly costs? The NVIDIA API likely charges per-token. With 128K context windows, a single complex task could cost significant tokens.
sure

**Q3.6 — Context Window Management:** KIMI K2 has 128K tokens, but that doesn't mean we should use all of it. The architecture specifies a 3-tier memory pipeline. What's the maximum tokens we should inject per LLM call? Proposed: 8K tokens for routing decisions, 32K tokens for document generation, 64K tokens for full-month summaries. Sound reasonable?
this sounds resonable
---

## SECTION 4: GOOGLE DRIVE INTEGRATION (The File Vault)

**Q4.1 — Service Account Confirmation:** We're going with a Google Service Account (not OAuth). This means we create a bot-owned Drive. You will need to "share" specific folders with the Service Account's email (like `bot@project.iam.gserviceaccount.com`) so it can write there. Are you comfortable with this setup, or do you need the bot to write directly into YOUR personal/company Google Drive?
we can do it on my personal google drive a small guide will help 

**Q4.2 — Folder Hierarchy:** Proposed structure. Confirm or modify:
```
PacificUnity_Bot/
├── Vendors/
│   ├── List_Of_Vendors/
│   │   ├── Quotes/
│   │   ├── POs/
│   │   └── Technical_Drawings/
│   ├── Cromonimet_Steel/
│   └── Magizhini_Enterprises/
├── Projects/
│   ├── 3M_Liter_Tank/
│   ├── Bottle_Filling_Line/
│   └── Electrical_Installation/
├── Generated_Documents/
│   ├── Proforma_Invoices/
│   ├── Commercial_Quotations/
│   └── Letterhead_Documents/
├── Chat_Backups/
│   └── Daily_Summaries/
└── System/
    └── DB_Backups/
```

Magizhini_Enterprises is one vendor, we cannot make different folders everytime because we have multiple vendors product/project based approach is more apt 

**Q4.3 — Duplicate File Handling:** If the same PDF (e.g., "MAGIZHINI OFFER 142") is shared in WhatsApp twice (once in the group, once in personal chat), should we: (a) store both copies (wastes space), (b) detect the duplicate by hash and skip (saves space but risks missing a genuinely updated version with the same name), or (c) store both but flag the duplicate in the metadata?

There are cases where two files same name but the latest one is edited. It really depends because in my opinion 90% of the time it is the latest file that needs saving but then again we might need to save the one before that as well. 

**Q4.4 — File Retention Policy:** Should files on Drive be kept forever, or should we auto-archive after X months? Given Drive's 15GB free tier per Service Account, large CAD drawings (2MB+) will accumulate. Do you have Google Workspace with unlimited storage, or are we on the free tier?

No let it be forever, while we do have 1 TB of storage through microsoft one drive . so store there or use the 50GB of space I have on my personal account anything is fine, I am just a bit more familiar with googles set up process 

**Q4.5 — Upload Failure Recovery:** If a file upload to Drive fails mid-transfer (network issue, token expiry), should we: (a) retry 3 times with exponential backoff, then alert you on WhatsApp, or (b) queue it for the next cron cycle? The local `/tmp/` copy must NOT be deleted until upload is confirmed.

retry 3 times with exponential backoff, then alert you on WhatsApp. if failed after 3 attempts then queue it for the next cron cycle? The local `/tmp/` copy must NOT be deleted until upload is confirmed.
---

## SECTION 5: THE CHASER ENGINE (Persistent Follow-ups)

*This is the system's most operationally sensitive component. A broken Chaser means tasks silently die.*

**Q5.1 — Escalation Timing Matrix:** The architecture proposes T+12h → WhatsApp nudge, T+24h → firm chase, T+48h → email escalation. But your team operates across India (IST, UTC+5:30) and Africa (multiple timezones, EAT UTC+3, WAT UTC+1). Should nudge timing be based on: (a) absolute hours from task creation (current design), (b) "business hours" of the assignee's timezone, or (c) absolute hours but with a "quiet window" (e.g., no nudges between 11 PM - 7 AM local)?
keep a quiet window of 2AM TO 8 AM IST. work otherthan that full

**Q5.2 — Task Priority Tiers:** Not all tasks are equal. "Pay 25K to Shahid" (financial, urgent) vs "Buy domain" (administrative). Should we have priority tiers that adjust Chaser timing?
- **P0 (Critical/Financial):** Nudge at T+2h, escalate at T+6h
- **P1 (Standard Operations):** Nudge at T+12h, escalate at T+24h
- **P2 (Administrative):** Nudge at T+24h, escalate at T+72h
yeah try to autodecide that

**Q5.3 — Manual Override:** Can "Dad Africa" or you (Shreyas) manually mark a task as "Paused" or "Cancelled" via WhatsApp command? (e.g., replying "Cancel task: Buy domain" stops the Chaser). Or should this only be possible from the dashboard?
yeah we can do that through whatsapp and dashboard both

**Q5.4 — Chaser Message Style:** Should the nudge messages be: (a) LLM-generated (natural, varied language but costs tokens and risks hallucination), (b) hardcoded templates with variable injection (e.g., "Reminder: {task} assigned to {person} is overdue by {hours}h"), or (c) LLM-generated once at task creation, then cached?
we can do either way I feel like hardcoded dynamic injections is easier as it will take less api cost and lesser headache same results 

**Q5.5 — Duplicate Nudge Prevention:** If the Chaser cron fires at 1:00 PM and the nudge takes 5 seconds to send, but the cron fires again at 1:00 PM (Docker restart, clock skew), how do we prevent double nudges? Proposed: a `last_nudged_at` timestamp column with a minimum 55-minute gap enforced at the query level.
yeah please lets do what you propsed 


**Q5.6 — Task Completion Detection:** How does the bot know a task is "done"? Options: (a) Assignee replies with a keyword ("Done", "Completed", "Paid"), (b) Assignee uploads the requested deliverable (e.g., sends the video that was requested), (c) Explicit button/command on the dashboard. Current design assumes (a). Is that sufficient, or do we need (b) and (c) as well?


we could add c, i am not sure what you mean by b, but we can just say ok or done and it should be okay


---

## SECTION 6: EMAIL ESCALATION (Outlook SMTP)

**Q6.1 — Authentication Method:** Outlook/Microsoft 365 SMTP requires either: (a) Basic Auth (username + app password) -- Microsoft is deprecating this, or (b) OAuth2 with MSAL (Modern Authentication). Which does `info@stelastra.com` support? If it's on Microsoft 365 Business, we'll need to register an Azure AD app for OAuth2 tokens.
yeah it is a 365 buisness account

**Q6.2 — Sending Limits:** Microsoft 365 has a default limit of 10,000 emails/day and 30 messages/minute. Given the Chaser's escalation patterns, this should be fine, but are there any custom restrictions on your account?
this is fine

**Q6.3 — Email Content:** For escalation emails, do you want: (a) plain text only, (b) styled HTML matching the Pacific Unity brand, or (c) HTML with the generated document (e.g., the overdue PO) attached as a PDF?
plain text works 

**Q6.4 — CC/BCC Rules:** The architecture says CC "Dad Africa" on escalations. Should ALL escalation emails CC Dad Africa, or only P0 (critical) ones? Should Shreyas always be CC'd?
shreyas should always be cced and crictical ones dad africa 

---

## SECTION 7: SECURITY & DATA HANDLING

*Your raw chat data contains OTPs, credit card references, bank account details, and personal phone numbers. This section is non-negotiable.*

**Q7.1 — PII Redaction:** The `I have an idea.md` dump contains: an OTP (`886220`), a card reference (`ending 3447`), IndusInd Bank transaction details, and personal phone numbers. Before storing messages in SQLite, should the Ingress Parser automatically detect and redact sensitive data patterns (OTPs, card numbers, bank refs)? Or do you want everything stored verbatim for auditability?
yeah that must happen


**Q7.2 — Access Control:** Who should be able to query the bot for information? If Govind asks "What was the pricing Imran quoted?", should he see it? What about Shibu? Is there a role hierarchy where some data is restricted? Proposed roles:
No all can see

- **Admin (Dad Africa, Shreyas):** Full access to all data, all chats, all documents
- **Employee (Govind, Shibu, Kumutha):** Access to their own tasks + project-level documents they're involved in
- **External (Imran, Karthik):** Access only to documents directly shared with them

**Q7.3 — VPS Security Hardening:** The DigitalOcean VPS will be exposed to the internet (for webhooks). Minimum hardening checklist: SSH key-only auth (no passwords), UFW firewall (only ports 80/443 open), fail2ban, automatic security updates. Are you comfortable with this, or do you have existing security preferences?
I think this should be fine right? basic protection should be good, what do you suggest

**Q7.4 — HTTPS Certificates:** For the webhook endpoint, we need HTTPS. Proposed: Caddy reverse proxy with automatic Let's Encrypt certificates. This requires a domain name pointing to the VPS. Which domain will you use? (e.g., `api.pacificunity.ae`, `bot.stelastra.com`)
we can use bot.stealastra.com, just tell me how to set it up, I have a domain on ftplgh.com live and I have the domain for stelastra.com but no website no it yet

---

## SECTION 8: CONTEXT BUFFER & MULTI-CHAT ISOLATION

*The "shopping cart" concept from the Architecture Whitepaper needs precise rules.*

**Q8.1 — Session Timeout:** The architecture proposes a 10-minute buffer window for multi-file drops. Is 10 minutes right? If someone sends 2 PDFs, goes to make coffee, and sends the 3rd PDF 15 minutes later, should the buffer: (a) have already closed and processed only 2 PDFs, or (b) be smart enough to re-open if the same "intent" is detected?

I think it needs to be smart enough to re-open if the intent is detected and also give an option on the dashboard to work on this


**Q8.2 — Cross-Chat Context Isolation:** If Dad Africa discusses a confidential pricing negotiation with Imran in a personal chat, and then someone asks in the main group "What's the latest price for Zincalume?", should the bot: (a) share the price from the private chat (dangerous), (b) only reference data shared IN the group context (safe but potentially incomplete), or (c) ask Dad Africa for permission before surfacing private data?

Option C 



**Q8.3 — Concurrent Sessions:** What if Dad Africa is simultaneously: (a) uploading files for a Proforma in the project group, and (b) asking about steel prices in the personal chat? These are two parallel sessions from the same user. How many concurrent buffers per user should we support? Proposed: unlimited, keyed by `(user_id, chat_id, intent_hash)`.
yes please goahead with this 

**Q8.4 — Buffer Trigger Keywords:** What explicit keywords should trigger the context buffer to "open" and start collecting? Proposed defaults:
- "Compare these..." → opens multi-file collection buffer
- "Generate..." / "Make..." / "Create..." → opens document generation buffer
- "Check prices for..." → opens data retrieval session

Should the bot also send a confirmation? (e.g., "Got it, I'm collecting files. Send me everything and say 'Done' when ready, or I'll process in 10 minutes.")

We need to be able to use @bot_name and then it will do whatever it says could be generate, compare, check price 

---

## SECTION 9: DOCUMENT GENERATION & BRAND COMPLIANCE

**Q9.1 — Template Source Files:** Do you already have DOCX templates for: (a) Commercial Quotation, (b) Proforma Invoice, (c) Company Letterhead? If yes, can you upload them to the workspace so we can programmatically inject variables? If not, should the bot generate them from scratch using the `brand-guidelines` skill?
yeah we have some so We also need to look at packing list and invoice, I will enter them in a place which feels right for you

**Q9.2 — Brand Assets:** Does Pacific Unity MEA FZ-LLC have: a logo file (PNG/SVG), official color codes (hex), official font name, and registered address? These are needed for the `brand-guidelines` and `theme-factory` skills.
so we are a group company called North Star Impex and under is comes North Star Impex Group Company : NSI Projects Fine Techno Pack (ftpl), Stel Astra, NSI China, Pacific Unity, North Star Impex Kenya, North Star Impex West Africa

**Q9.3 — Currency Handling:** Your operations span INR (₹), USD ($), AED, and potentially KES (Kenyan Shilling). When generating invoices, should the bot: (a) use the currency mentioned in the conversation, (b) always convert to a base currency (USD?), or (c) ask which currency to use? How do we handle exchange rates -- hardcoded monthly rate, or live API?
yeah so we will hardcode the rate, mostly it'll be converted to USD though, for example current rate is 91 


**Q9.4 — Document Approval Workflow:** When the bot generates a Proforma Invoice, proposed flow:
1. Bot generates draft → sends as PDF to the WhatsApp chat
2. Decision maker replies "Approved" or "Change X to Y"
3. If "Change": bot regenerates with modifications
4. If "Approved": bot marks as final, uploads to Drive, logs in SQLite
Is this flow correct? Who specifically has approval authority?
yeah this is good, whoever is chatting has approval authority, 
---

## SECTION 10: EMPLOYEE DASHBOARD

**Q10.1 — Authentication Specifics:** You confirmed Magic Links. How should they work? Proposed: Every morning at 8 AM (or configurable time), the bot sends each employee a unique URL via WhatsApp. The URL contains a JWT token valid for 24 hours. No passwords, no accounts. Is this acceptable?
I am not sure, prefereably keep it easy because magic links will make it harder. nobody is opening their email all the time, a simple password should be okay

**Q10.2 — Dashboard Features Priority:** Rank these 1-5 (1 = must-have for V1, 5 = nice-to-have for later):
- [1] Task list (assigned to me, overdue, completed)
- [2] File upload portal (bypass WhatsApp's 16MB limit)
- [1] Chat interface (1-on-1 with the bot, pre-loaded with my tasks)
- [1] Analytics view (tasks per employee, bottlenecks, average completion time)
- [1] Document search (find any vendor quote or generated invoice)

**Q10.3 — Mobile Responsiveness:** Employees will likely access the dashboard on their phones. Should we prioritize mobile-first design, or is desktop access primary?

we can do mobile first design

**Q10.4 — Hosting:** The architecture suggests serving static files from the FastAPI backend. But you also mentioned Vercel/Netlify. Which do you prefer? Vercel/Netlify means the frontend is decoupled (better performance, global CDN) but adds a CORS configuration step. FastAPI-served means simpler but slower and uses VPS resources.

Yeah do whatever is simpler and easier 

---

## SECTION 11: DEPLOYMENT, MONITORING & OPERATIONS

**Q11.1 — Domain for Webhook Endpoint:** Which domain/subdomain will point to the VPS? (e.g., `bot.pacificunity.ae`, `api.stelastra.com`). This is needed for HTTPS and for OpenClaw webhook registration.
we can do bot.stelastra.com but I will need your help to set it up

**Q11.2 — Monitoring & Alerting:** If the bot silently crashes at 3 AM, how should you be notified? Options: (a) Uptime monitor (UptimeRobot, free tier) pings the health endpoint every 5 minutes and emails/SMSes you, (b) The bot itself sends a "heartbeat" message to a private WhatsApp chat every hour -- if you stop receiving it, something is wrong. (c) Both. **Recommendation: (c) Both.**

yeah do both

**Q11.3 — Log Management:** On a 25GB SSD, logs can fill up the disk and crash the server. Proposed: structured JSON logs with a 7-day retention policy, rotated daily, max 500MB total. Old logs are uploaded to Drive before deletion. Acceptable?
yeah that works 

**Q11.4 — Deployment Strategy:** Current plan is `git pull && docker-compose up --build -d`. During the ~30 seconds of rebuild, the bot is offline and webhooks may be lost. Options: (a) Accept the downtime (simple), (b) Blue-green deployment with two containers and a load balancer (complex, more RAM), (c) Deploy during low-traffic hours only (e.g., 4 AM IST). What's your preference?

yeah do it during silent time at 4AM IST

**Q11.5 — CI/CD:** Do you want automated deployment on `git push` to main? (GitHub Actions → SSH into VPS → rebuild). Or manual deployment only?

we ccould do manual

---

## SECTION 12: WHATSAPP PARSER EDGE CASES

*The raw data in `I have an idea.md` is genuinely chaotic. These questions determine parser robustness.*

**Q12.1 — Forwarded Messages:** WhatsApp shows "Forwarded" as a label. Should forwarded messages be treated the same as original messages, or flagged differently? (A forwarded vendor quote might not be "new" -- it could be a re-share of something already processed.)

yeah sure 

**Q12.2 — Deleted Messages:** The dump contains `"This message was deleted"`. Should we: (a) ignore deleted messages entirely, (b) log that a deletion occurred (for audit trail), or (c) try to infer what was deleted from surrounding context?
yeah ignore deteleted 

**Q12.3 — Voice Notes & Videos:** WhatsApp users send voice notes and videos. Does OpenClaw deliver these? If yes, should we: (a) transcribe voice notes via Whisper API, (b) ignore them, or (c) acknowledge receipt but flag for manual review?
OpenClaw delivers WhatsApp voice notes and videos as media payloads, with native support for audio (including PTT voice notes in ogg/opus format) and video.
Recommendation

Choose (a) transcribe voice notes via Whisper API using OpenClaw's official Whisper plugin or local MLX variant—this injects transcribed text directly into the agent context for natural processing.
Handling Options

    Voice Notes: Install @agentclaws/openclaw-whisper plugin for automatic transcription (supports Groq/OpenAI/local Whisper); audio saves to ~/.openclaw/media/inbound/ and becomes [Voice] transcribed text.

    Videos: Acknowledge receipt (e.g., "Received video—summarizing content") and flag for manual review or use vision models if integrated; no built-in video transcription, but media delivery works.​​

    Why not others? Ignoring loses value; manual flagging alone skips AI automation—transcription maximizes utility for your data analytics/AI setup.



**Q12.4 — Language Detection:** The chats are primarily in English, but some messages have Hindi/regional language phrases. Should the parser: (a) assume English only, (b) detect language and translate non-English content, or (c) store verbatim and only translate on-demand?
it can be english, hindi both of these are the input but output must be english

**Q12.5 — Group Metadata Events:** WhatsApp generates system messages like "Dad Africa added Kumutha" or "You were added". Should we parse these for team membership tracking (automatically updating the employee roster)?
yeah please just ask a conformation before doing
---

## SECTION 13: SCOPE BOUNDARIES & V1 DEFINITION

*This is arguably the most important section. It prevents scope creep.*

**Q13.1 — What is V1?** We need to ship something functional before perfecting everything. Proposed V1 scope (4-6 weeks):
1. Webhook ingress + message parsing + SQLite storage
2. Basic intent routing (document request, task assignment, file upload)
3. Google Drive file sync (upload, link storage, local cleanup)
4. The Chaser (task tracking + WhatsApp nudges only, no email yet)
5. One document template (Proforma Invoice)
6. Static employee dashboard (task list only)


**What is explicitly NOT in V1:**
- Email escalation (V1)
- Full graph RAG querying (V2)
- Analytics dashboard (V1)
- Voice note transcription (V2)
- Auto-generated daily EOD reports (V1)
- Dubizzle/web scraping (V2)

**Does this phasing make sense? What would you move into or out of V1?**

**Q13.2 — Success Criteria:** How do we know V1 works? Proposed: (a) Bot successfully parses a real WhatsApp message and stores it, (b) Bot generates a correct Proforma Invoice from a chat command, (c) Bot assigns a task and sends a nudge after the deadline, (d) A file sent on WhatsApp appears in the correct Drive folder within 60 seconds.
all of the above

**Q13.3 — Who Tests?** During development, will you (Shreyas) be the sole tester, or will Dad Africa / Govind also test? This determines whether we need a staging environment or can test in production.
I will be the sole testor at first 

---

## SECTION 14: COST & RESOURCE BUDGET

**Q14.1 — Monthly Budget:** What's the maximum monthly spend you're comfortable with for this system? Approximate breakdown:
- DigitalOcean VPS: ~$6/month (GitHub Student)
- Domain: ~$1-3/month (amortized)
- NVIDIA API (KIMI K2): Variable -- depends on usage. Estimate? we have around  5,000 free API credits loaded 
- Google Drive: Free tier (15GB) or Workspace, free tier but I have 
- OpenClaw: Free tier or paid? this is open source 



**Q14.2 — NVIDIA API Credits:** Do you have free credits from NVIDIA (developer program, hackathon, etc.)? Or is this pay-per-token from day one? 5,000 free API credits

**Q14.3 — Time Investment:** How many hours per week can you dedicate to reviewing bot outputs, approving documents, and providing feedback during the development phase? not much we need a feedbacj generator as well 

---

*Once you've filled in these answers, I will generate:*
1. **`PRD.md`** — The locked Product Requirements Document
2. **`architecture_v2.md`** — The finalized, production-ready architecture
3. **`IMPLEMENTATION_PLAN.md`** — A week-by-week build plan with milestones
