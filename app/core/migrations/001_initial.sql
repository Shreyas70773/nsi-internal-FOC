CREATE TABLE IF NOT EXISTS processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT,
    chat_type TEXT,
    sender_id TEXT,
    sender_name TEXT,
    timestamp DATETIME,
    type TEXT,
    content TEXT,
    content_hash TEXT,
    media_id TEXT,
    media_filename TEXT,
    media_mime TEXT,
    is_forwarded BOOLEAN DEFAULT 0,
    is_bot_mention BOOLEAN DEFAULT 0,
    bot_command TEXT,
    language TEXT DEFAULT 'en',
    metadata TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp ON messages (chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages (sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_bot_mention ON messages (is_bot_mention) WHERE is_bot_mention = 1;

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    whatsapp_id TEXT UNIQUE,
    name TEXT,
    role TEXT CHECK (role IN ('admin', 'employee', 'external')),
    email TEXT,
    timezone TEXT DEFAULT 'Asia/Kolkata',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (name);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES entities (id),
    target_id TEXT NOT NULL REFERENCES entities (id),
    relation_type TEXT,
    metadata JSON DEFAULT '{}',
    source_message_id TEXT REFERENCES messages (id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, target_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships (source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships (target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships (relation_type);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    assigner_id TEXT REFERENCES employees (id),
    assignee_id TEXT NOT NULL REFERENCES employees (id),
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'P1',
    status TEXT DEFAULT 'pending',
    source_chat_id TEXT,
    source_message_id TEXT REFERENCES messages (id),
    deadline DATETIME,
    completed_at DATETIME,
    last_nudged_at DATETIME,
    nudge_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS idx_tasks_status_nudge ON tasks (status, last_nudged_at);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT,
    mime_type TEXT,
    file_hash TEXT,
    file_size_bytes INTEGER,
    drive_url TEXT,
    drive_file_id TEXT,
    folder_path TEXT,
    source_chat_id TEXT,
    source_message_id TEXT REFERENCES messages (id),
    uploaded_by TEXT REFERENCES employees (id),
    project TEXT,
    doc_type TEXT,
    description TEXT,
    extracted_text TEXT,
    duplicate_of TEXT REFERENCES documents (id),
    status TEXT DEFAULT 'pending_upload',
    local_path TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents (file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents (project);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);

CREATE TABLE IF NOT EXISTS context_buffers (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    chat_id TEXT,
    intent TEXT,
    intent_hash TEXT,
    status TEXT DEFAULT 'collecting',
    message_ids JSON DEFAULT '[]',
    media_ids JSON DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    timeout_minutes INTEGER DEFAULT 10,
    UNIQUE (user_id, chat_id, intent_hash)
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id TEXT PRIMARY KEY,
    doc_type TEXT,
    brand TEXT,
    status TEXT DEFAULT 'draft',
    template_used TEXT,
    variables_json TEXT,
    self_eval_score REAL,
    self_eval_issues TEXT,
    drive_url TEXT,
    drive_file_id TEXT,
    requested_by TEXT REFERENCES employees (id),
    approved_by TEXT REFERENCES employees (id),
    source_chat_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT,
    model TEXT,
    request_type TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    cost_estimate_usd REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_token_usage_provider_date ON token_usage (provider, created_at);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id TEXT PRIMARY KEY,
    chat_id TEXT,
    period_start DATETIME,
    period_end DATETIME,
    summary TEXT,
    extracted_facts JSON DEFAULT '[]',
    message_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conv_summaries_chat_period ON conversation_summaries (chat_id, period_end);

CREATE TABLE IF NOT EXISTS privacy_permissions (
    id TEXT PRIMARY KEY,
    data_owner_id TEXT REFERENCES employees (id),
    data_type TEXT,
    data_reference TEXT,
    requested_by_chat_id TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

CREATE TABLE IF NOT EXISTS dashboard_sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT REFERENCES employees (id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);
