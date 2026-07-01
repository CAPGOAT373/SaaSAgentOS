# Sprint 3 -- Real API Integration

Branch: sprint-3
Status: Complete
Commit: TBD (pending Task 3.7)
Tag: v0.3.0 (pending Task 3.7)
Date: 2026-07-01

## Goals
- Build unified Axios API client
- Connect real JWT login
- Migrate Task Center to real API

## Completed Tasks

### Task 3.1 -- Axios API Client
- Created src/api/axios-client.ts with JWT interceptors
- AxiosApiError typed error class, SSR-safe localStorage access
- Unified request/response interceptors

### Task 3.2 -- Real JWT Login
- Switched login to Axios, localStorage token persistence
- authStore.login() writes auth_token, tenant_id, user_id
- authStore.hydrate() restores session from localStorage
- authStore.logout() clears storage and state

### Task 3.3 -- Task Center Real API
- Tasks list and detail connected to FastAPI via Axios
- Backend endpoints: GET /api/v1/tasks, GET /api/v1/tasks/{id}
- Loading, error, and empty states covered

### Task 3.4 -- Verification
- All 5 API endpoints tested: login (200), tasks list (200), task detail (200), non-existent (404), no-auth (403)
- Code review: all 6 Sprint 3 files verified

### Task 3.5 -- Code Review & Cleanup
- Removed dead import of old api client from login page
- Added @deprecated annotation to client.ts, pointing to axios-client
- Verified axios version consistency (^1.7.7 -> 1.18.1)

### Task 3.6 -- Documentation Sync
- Updated docs/sprints/sprint-3.md (this file)
- Updated CHANGELOG.md, AI_HANDOFF.md, PROJECT_STATUS.md, ROADMAP.md

### Task 3.7 -- Git Freeze (pending)
- git add / commit / tag v0.3.0 / push

## Directory Changes
A frontend-next/src/api/axios-client.ts  (Task 3.1)
M frontend-next/package.json             (Task 3.1, axios dep)
M frontend-next/src/api/index.ts         (Task 3.1, barrel)
M frontend-next/src/api/client.ts        (Task 3.5, @deprecated)
M frontend-next/src/app/login/page.tsx   (Task 3.2, 3.5)
M frontend-next/src/app/tasks/page.tsx   (Task 3.3)
M frontend-next/src/app/tasks/[id]/page.tsx (Task 3.3)

## Known Limitations
- Task Center create/retry/cancel not implemented (backend lacks endpoints)
- Other pages (Dashboard, Agents, Workflows, etc.) still use mock data
- Backend uses in-memory storage (no database persistence)
- client.ts kept for backward compatibility but is deprecated

## Next Steps
- Execute Task 3.7 (Git freeze with commit and tag)
- Begin Sprint 4: Frontend architecture cleanup per master plan
