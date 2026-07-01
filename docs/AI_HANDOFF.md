# Agent OS V6.0 -- AI Handoff

## One-Liner
Agent OS is a multi-tenant AI agent economy platform with FastAPI backend and Next.js frontend. Sprint 3 complete -- Login and Task Center on real API, all other pages on mock data.

## Current State
- Sprint: 3 COMPLETE (pending git freeze)
- Branch: sprint-3
- Latest Commit: TBD (Sprint 3, pending Task 3.7)
- Latest Tag: v0.3.0 (pending)
- Frontend: 10 routes functional, Login + Tasks on real API, rest on mock
- Backend: Running on 127.0.0.1:8001, in-memory data

## Completed
- Sprint 0: FastAPI backend, Swagger, JWT auth
- Sprint 1: Next.js 14, Zustand, Layout, Router, 10 routes
- Sprint 2: Mock data unification, all HTTP 500 fixed
- Sprint 3: Axios client, real JWT login, Task Center real API, code cleanup

## In Progress
- Sprint 3 Task 3.7: Git freeze (commit, tag v0.3.0, push)

## Next Steps
- Execute Task 3.7: Git commit + tag v0.3.0 + push
- Begin Sprint 4: Frontend architecture cleanup (API resource layer, feature separation, UI state components, formatters)
- Align with master execution plan (14 stages, M1-M8 milestones)

## Risks & Technical Debt
- Backend in-memory storage: all data lost on restart
- No database persistence (SQLAlchemy configured but not used)
- Next.js proxy turns 401 into 500 for error responses
- Port 8000 occupied by Windows svchost; backend on 8001
- Legacy client.ts kept for backward compatibility (deprecated)
- 8/10 pages still on mock data (Dashboard, Agents, Workflows, Files, Models, Settings, Marketplace, Billing)

## Key Directories
| Directory | Purpose |
|---|---|
| agent_os/ | FastAPI backend |
| frontend-next/ | Next.js frontend (active) |
| frontend/ | Legacy Vite frontend (reference only) |
| docs/ | Project documentation |
| deploy/ | Docker, K8s, Helm, Istio configs |

## Key Commands
`
# Backend
cd E:\SaaSAgentOS\SaaSAgentOS
=8001; python -m agent_os.main

# Frontend
cd frontend-next
npm run dev

# Login
tenant=agentos, email=admin@agentos.local, password=Admin123!
`

## AI Working Rules
1. Read docs first: Start with this file, then PROJECT_OVERVIEW.md, ARCHITECTURE.md, ROADMAP.md
2. Don't guess requirements: If information is missing, ask or mark as TBD
3. Don't refactor arbitrarily: Follow existing patterns (AuthGuard, AppLayout, mock data)
4. Understand context before modifying: Read the relevant sprint doc and page code
5. Mock vs Real: Login is real API; Tasks is real API; all others are mock data
6. Axios for API: Use axiosInstance from @/api for all HTTP calls
7. Don't delete mock data: Mock layer coexists with real API
8. Don't modify backend: Backend is FastAPI, changes require explicit task
9. Legacy client.ts is DEPRECATED: Use axiosInstance from ./axios-client instead
