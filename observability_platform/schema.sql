-- ============================================================
-- AI Agent Observability Platform - PostgreSQL Schema
-- Tables: traces, spans, events, logs, metrics, llm_calls,
-- tool_calls, rag_queries, prompt_versions, cost_records, errors, security_alerts
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── Traces ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS traces (
    trace_id        VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name            VARCHAR(256) NOT NULL,
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    user_id         VARCHAR(64) DEFAULT '',
    root_span_id    VARCHAR(64) DEFAULT '',
    start_time      DOUBLE PRECISION NOT NULL,
    end_time        DOUBLE PRECISION DEFAULT 0,
    duration_ms     DOUBLE PRECISION DEFAULT 0,
    status          VARCHAR(16) DEFAULT 'running',
    error_count     INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    total_cost      DOUBLE PRECISION DEFAULT 0.0,
    risk_score      DOUBLE PRECISION DEFAULT 0.0,
    alert_level     VARCHAR(16) DEFAULT 'none',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_traces_tenant ON traces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_start ON traces(start_time DESC);

-- ── Spans ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS spans (
    span_id         VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
    parent_span_id  VARCHAR(64) DEFAULT '',
    name            VARCHAR(256) NOT NULL,
    type            VARCHAR(16) DEFAULT 'agent',
    service         VARCHAR(64) DEFAULT '',
    status          VARCHAR(16) DEFAULT 'running',
    start_time      DOUBLE PRECISION NOT NULL,
    end_time        DOUBLE PRECISION DEFAULT 0,
    duration_ms     DOUBLE PRECISION DEFAULT 0,
    tags            JSONB DEFAULT '{}',
    events          JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    input           JSONB,
    output          JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_type ON spans(type);

-- ── Events (Event Sourcing) ──────────────────────────
CREATE TABLE IF NOT EXISTS events (
    event_id        VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) DEFAULT '',
    span_id         VARCHAR(64) DEFAULT '',
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    event_type      VARCHAR(32) NOT NULL,
    payload         JSONB DEFAULT '{}',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- ── Logs ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS logs (
    log_id          VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) DEFAULT '',
    span_id         VARCHAR(64) DEFAULT '',
    tenant_id       VARCHAR(64) NOT NULL,
    level           VARCHAR(8) DEFAULT 'info',
    message         TEXT DEFAULT '',
    payload         JSONB DEFAULT '{}',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_logs_trace ON logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_logs_tenant ON logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);

-- ── LLM Calls ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id             VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id            VARCHAR(64) DEFAULT '',
    span_id             VARCHAR(64) DEFAULT '',
    tenant_id           VARCHAR(64) NOT NULL,
    agent_id            VARCHAR(64) DEFAULT '',
    model               VARCHAR(64) DEFAULT '',
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    latency_ms          DOUBLE PRECISION DEFAULT 0,
    cost                DOUBLE PRECISION DEFAULT 0,
    quality_score       DOUBLE PRECISION DEFAULT 0,
    prompt              TEXT DEFAULT '',
    response            TEXT DEFAULT '',
    status              VARCHAR(16) DEFAULT 'ok',
    timestamp           DOUBLE PRECISION NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_llm_trace ON llm_calls(trace_id);
CREATE INDEX IF NOT EXISTS idx_llm_tenant ON llm_calls(tenant_id);
CREATE INDEX IF NOT EXISTS idx_llm_model ON llm_calls(model);

-- ── Tool Calls ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_calls (
    call_id             VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id            VARCHAR(64) DEFAULT '',
    span_id             VARCHAR(64) DEFAULT '',
    tenant_id           VARCHAR(64) NOT NULL,
    agent_id            VARCHAR(64) DEFAULT '',
    tool_name           VARCHAR(128) NOT NULL,
    input               JSONB,
    output              JSONB,
    latency_ms          DOUBLE PRECISION DEFAULT 0,
    error               TEXT DEFAULT '',
    permission_granted  BOOLEAN DEFAULT TRUE,
    status              VARCHAR(16) DEFAULT 'ok',
    timestamp           DOUBLE PRECISION NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tool_trace ON tool_calls(trace_id);
CREATE INDEX IF NOT EXISTS idx_tool_tenant ON tool_calls(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_calls(tool_name);

-- ── RAG Queries ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS rag_queries (
    query_id                VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id                VARCHAR(64) DEFAULT '',
    span_id                 VARCHAR(64) DEFAULT '',
    tenant_id               VARCHAR(64) NOT NULL,
    agent_id                VARCHAR(64) DEFAULT '',
    query                   TEXT DEFAULT '',
    embedding_dim           INTEGER DEFAULT 0,
    vector_search_results   INTEGER DEFAULT 0,
    rerank_scores           JSONB DEFAULT '[]',
    retrieved_docs          JSONB DEFAULT '[]',
    latency_ms              DOUBLE PRECISION DEFAULT 0,
    status                  VARCHAR(16) DEFAULT 'ok',
    timestamp               DOUBLE PRECISION NOT NULL,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rag_trace ON rag_queries(trace_id);
CREATE INDEX IF NOT EXISTS idx_rag_tenant ON rag_queries(tenant_id);

-- ── Prompt Versions ──────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_versions (
    version_id      VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    prompt_name     VARCHAR(128) DEFAULT '',
    version         VARCHAR(32) DEFAULT '1.0.0',
    template        TEXT DEFAULT '',
    variables       JSONB DEFAULT '{}',
    rendered        TEXT DEFAULT '',
    output          TEXT DEFAULT '',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prompt_tenant ON prompt_versions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_prompt_agent ON prompt_versions(agent_id);

-- ── Cost Records ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_records (
    record_id       VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) DEFAULT '',
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    workflow_id     VARCHAR(64) DEFAULT '',
    component       VARCHAR(16) DEFAULT 'llm',
    tokens          INTEGER DEFAULT 0,
    cost            DOUBLE PRECISION DEFAULT 0.0,
    currency        VARCHAR(8) DEFAULT 'USD',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cost_tenant ON cost_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cost_trace ON cost_records(trace_id);
CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_records(agent_id);

-- ── Errors ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS errors (
    error_id        VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) DEFAULT '',
    span_id         VARCHAR(64) DEFAULT '',
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    error_type      VARCHAR(128) DEFAULT '',
    message         TEXT DEFAULT '',
    stack           TEXT DEFAULT '',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_err_trace ON errors(trace_id);
CREATE INDEX IF NOT EXISTS idx_err_tenant ON errors(tenant_id);

-- ── Security Alerts ──────────────────────────────────
CREATE TABLE IF NOT EXISTS security_alerts (
    alert_id        VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    trace_id        VARCHAR(64) DEFAULT '',
    tenant_id       VARCHAR(64) NOT NULL,
    agent_id        VARCHAR(64) DEFAULT '',
    risk_type       VARCHAR(32) DEFAULT '',
    risk_score      DOUBLE PRECISION DEFAULT 0,
    alert_level     VARCHAR(16) DEFAULT 'low',
    auto_block      BOOLEAN DEFAULT FALSE,
    detail          TEXT DEFAULT '',
    evidence        JSONB DEFAULT '{}',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sec_tenant ON security_alerts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sec_level ON security_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_sec_score ON security_alerts(risk_score DESC);

-- ── Metrics (aggregated) ─────────────────────────────
CREATE TABLE IF NOT EXISTS metrics (
    metric_id       VARCHAR(64) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    tenant_id       VARCHAR(64) NOT NULL,
    metric_name     VARCHAR(64) NOT NULL,
    metric_value    DOUBLE PRECISION NOT NULL,
    labels          JSONB DEFAULT '{}',
    timestamp       DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_metrics_tenant ON metrics(tenant_id);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
