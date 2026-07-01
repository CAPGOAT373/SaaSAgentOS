# Agent OS Architecture

## System Overview

```
Browser (localhost:3000)
  |
  v
Next.js 14 App Router (frontend-next/)
  |-- /api/* --> rewrite proxy --> FastAPI (127.0.0.1:8001)
  |-- All other routes --> mock data (services/mock/data.ts)
  |
  v
FastAPI / Uvicorn (agent_os/api_gateway/gateway.py)
  |-- 47+ REST endpoints
  |-- JWT auth (core_platform/identity/iam.py)
  |-- In-memory data stores
```

## Technical Architecture

### Backend (agent_os/)

```
agent_os/
  api_gateway/          FastAPI app, 47+ routes, CORS, rate limiter, WebSocket
  core_platform/        Domain logic (auth, billing, workflow, guardrail, etc.)
  ai_layer/             Agent runtime, LLM gateway, RAG, memory, reasoning
  services/             11 service classes (auth, agent, billing, workflow, ...)
  infra/                DB (SQLAlchemy stub), Redis, Kafka, observability
  marketplace/          Agent store, plugin store, pricing, revenue share
  config.py             AppConfig (multi-region, env vars)
  main.py               Entry point (uvicorn)
```

### Frontend (frontend-next/)

```
frontend-next/
  src/app/              10 page routes (App Router)
    page.tsx            Dashboard
    login/page.tsx      JWT login (Axios, real API)
    agents/             Agent list + detail (mock data)
    workflows/          Workflow list + detail (mock data)
    tasks/              Task list + detail (REAL API via Axios)
    files/              File management (mock data)
    models/             Model list + test (mock data)
    settings/           System settings (mock data)
    marketplace/        Agent marketplace (mock data)
    billing/            Billing overview (mock data)
  src/components/       Layout (Sidebar, Topbar, Breadcrumb, ThemeProvider)
  src/stores/           Zustand (authStore, uiStore)
  src/api/              API layer (client.ts, axios-client.ts, schema.ts, types.ts)
  src/services/mock/    Mock data for all pages (data.ts)
  src/lib/              Utilities (auth.ts, menu.ts)
```

### Frontend-Backend Communication

Login via POST /api/v1/auth/login to Next.js rewrite, then FastAPI, then JWT token
Tasks via GET /api/v1/tasks to Next.js rewrite, then FastAPI, then task list
Dashboard: imports from services/mock/data

All non-login pages (except Tasks): use frontend mock data
Tasks (Sprint 3): uses real API via Axios
