# Changelog

## v0.3.0 (pending Task 3.7) -- Sprint 3 Stable (2026-07-01)
- Task 3.1: Added Axios-based API client (axios-client.ts) with request/response interceptors, JWT injection, unified error handling (AxiosApiError)
- Task 3.2: Switched login page from fetch-based client to Axios; JWT persistence via Zustand authStore; auto-login on refresh
- Task 3.3: Connected Task Center (list + detail) to real FastAPI endpoints via Axios
- Task 3.4: End-to-end API verification (login, tasks list/detail, 404, 403)
- Task 3.5: Code review -- removed dead api import from login page, added @deprecated to legacy client.ts
- Task 3.6: Documentation sync (sprint-3.md, CHANGELOG.md, AI_HANDOFF.md, PROJECT_STATUS.md, ROADMAP.md)
- Task 3.7: Git freeze (pending)
- Commit: TBD

## v0.2.0 (2026-06-30) -- Sprint 2 Stable
- Migrated all pages from backend HTTP to frontend mock data
- Removed useAuth/token/authHeaders from all non-login pages
- Added Marketplace, Billing real mock data pages
- Fixed Settings, Models, Files, Tasks detail page 500 errors
- UTF-8 clean rewrite of tasks/[id]/page.tsx
- Commit: 4f4e2e1

## v0.1.0 (2026-06-28) -- Sprint 1 Stable
- Next.js 14 migration from Vite
- Zustand authStore + uiStore
- Layout: Sidebar, Topbar, Breadcrumb, ThemeProvider
- Auth: login page, AuthGuard, JWT
- 10 page routes (Dashboard, Agents, Workflows, Marketplace, Billing, Files, Models, Tasks, Settings)
- Menu system with role filtering
- Commit: 5631b1c
- Tag: sprint-1-stable
