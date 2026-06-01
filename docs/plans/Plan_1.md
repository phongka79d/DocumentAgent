# Plan 1 - Project Foundation

## 1. Goal

Create a runnable project foundation with a FastAPI backend, React TypeScript frontend, shared folder structure, configuration loading, logging, CORS, and a health check endpoint.

The goal is testable when the backend starts, the frontend builds, and `GET /api/health` returns a JSON response without requiring Supabase, Qdrant, ShopAIKey, document parsing, retrieval, or agents.

## 2. Why This Plan Exists

All later plans depend on a stable project layout and configuration pattern. This plan establishes where backend services, APIs, agents, tests, and frontend pages live so later implementation agents do not guess file locations or invent incompatible conventions.

## 3. Scope

- Create the backend FastAPI application skeleton.
- Create the frontend React + TypeScript skeleton.
- Add backend settings loading from environment variables.
- Add frontend environment configuration for the backend base URL.
- Add backend logging setup.
- Add CORS configuration for the local frontend.
- Add `GET /api/health`.
- Add backend and frontend `.env.example` files.
- Add minimal backend and frontend tests/build checks.
- Keep secrets backend-only by convention from the first milestone.

## 4. Out of Scope

- Do not implement Supabase clients or database access.
- Do not implement Supabase Storage upload.
- Do not implement Qdrant.
- Do not call ShopAIKey.
- Do not parse, chunk, embed, retrieve, or answer documents.
- Do not implement authentication, JWT, login, or multi-user support.
- Do not implement production deployment configuration.

## 5. Dependencies

- No previous plans are required.
- Requires Python and Node.js to be installed locally.

## 6. Required Files and Folders

```text
backend/app/main.py
- Creates the FastAPI app, includes routers, configures CORS, and exposes the application object.

backend/app/core/config.py
- Defines Settings with environment-driven configuration.

backend/app/core/logging.py
- Defines basic structured logging setup for backend startup and request debugging.

backend/app/api/__init__.py
- Marks the API package.

backend/app/api/health.py
- Contains the health check router.

backend/app/models/__init__.py
- Reserved package for shared Pydantic response models added in later plans.

backend/tests/test_health.py
- Verifies the health endpoint response contract.

backend/requirements.txt
- Lists FastAPI foundation dependencies.

backend/.env.example
- Shows backend environment variables without real secrets.

frontend/src/main.tsx
- React entrypoint.

frontend/src/App.tsx
- Minimal app shell that confirms frontend startup.

frontend/src/api/client.ts
- Axios client configured with `VITE_API_BASE_URL`.

frontend/src/styles.css
- Global Tailwind import or base CSS.

frontend/package.json
- Frontend scripts and dependencies.

frontend/tsconfig.json
- TypeScript compiler configuration.

frontend/vite.config.ts
- Vite configuration.

frontend/.env.example
- Shows frontend-safe environment variables.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Add one backend response schema:

```json
{
  "status": "ok",
  "service": "document-qa-agent",
  "app_env": "development"
}
```

The response can be implemented as a Pydantic model named `HealthResponse` in `backend/app/api/health.py` or in a shared model file if preferred.

## 8. API Design

```text
Method: GET
Path: /api/health
Request body: none
Response body:
{
  "status": "ok",
  "service": "document-qa-agent",
  "app_env": "development"
}
Error responses:
- 500 only if application startup/configuration fails unexpectedly.
Validation rules:
- No request validation is required.
```

## 9. Implementation Steps

1. Create backend folders: `backend/app`, `backend/app/api`, `backend/app/core`, `backend/app/models`, and `backend/tests`.
2. Create `backend/requirements.txt` with `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `httpx`, and `pytest`.
3. Implement `Settings` in `backend/app/core/config.py` with `APP_ENV`, `SINGLE_USER_ID`, and `FRONTEND_ORIGIN`.
4. Make `SINGLE_USER_ID` default to `single_user` and keep it backend-side.
5. Implement `setup_logging()` in `backend/app/core/logging.py` using Python logging with level `INFO`.
6. Implement `backend/app/api/health.py` with an `APIRouter` and `GET /health`.
7. Implement `backend/app/main.py` with `FastAPI(title="Document QA Agent")`, CORS middleware, health router mounted at `/api`, and startup logging.
8. Create `backend/.env.example` with only placeholders and no real keys.
9. Create frontend Vite React TypeScript files under `frontend/`.
10. Create `frontend/src/api/client.ts` using `axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL })`.
11. Create `frontend/.env.example` with `VITE_API_BASE_URL=http://localhost:8000`.
12. Create a minimal `App.tsx` that renders the app name and a placeholder for future routes.
13. Add `backend/tests/test_health.py` using `fastapi.testclient.TestClient`.
14. Run backend tests.
15. Run frontend install if needed, then build.

## 10. Configuration and Environment Variables

```text
APP_ENV
- Purpose: Selects development/test/production behavior.
- Required: No, default development.
- Example: development
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Fixed owner ID for all MVP data.
- Required: No, default single_user.
- Example: single_user
- Scope: Backend-only.

FRONTEND_ORIGIN
- Purpose: Allowed CORS origin for local frontend.
- Required: No, default http://localhost:5173.
- Example: http://localhost:5173
- Scope: Backend-only.

VITE_API_BASE_URL
- Purpose: Frontend base URL for backend API calls.
- Required: Yes for frontend runtime.
- Example: http://localhost:8000
- Scope: Frontend-safe.
```

## 11. Required Tests

Unit and integration checks:

```text
cd backend
pytest tests/test_health.py -v
```

Expected result:

```text
GET /api/health returns HTTP 200 and status "ok".
```

Manual backend check:

```text
uvicorn app.main:app --reload
curl http://localhost:8000/api/health
```

Frontend checks:

```text
cd frontend
npm install
npm run build
```

Expected result:

```text
TypeScript build succeeds.
No private backend keys are present in frontend files.
```

## 12. Acceptance Criteria

- Backend starts with `uvicorn app.main:app --reload`.
- `GET /api/health` returns HTTP 200.
- Health response includes `status`, `service`, and `app_env`.
- Backend settings load from `.env` and environment variables.
- Frontend builds successfully.
- `frontend/.env.example` contains only `VITE_API_BASE_URL`.
- No Supabase, Qdrant, or ShopAIKey logic exists yet.
- No Auth/JWT logic exists.
- No private keys are exposed in frontend code.

## 13. Failure Handling

- If `APP_ENV` is missing, default to `development`.
- If `SINGLE_USER_ID` is missing, default to `single_user`.
- If `FRONTEND_ORIGIN` is missing, default to the local Vite origin.
- If backend startup fails, the error must appear in logs.
- If frontend API base URL is missing at runtime, frontend requests may fail later, but build should still pass with `.env.example` documenting the variable.

## 14. Agent Report Requirement

The Execution Agent must report:

```text
Files created
Files modified
Commands run
Test results
Known issues
What was intentionally not implemented because it is out of scope
```

## 15. Reviewer Checklist

The Reviewer Agent must verify:

```text
Scope was followed
Out-of-scope work was not added
Tests were actually run
Acceptance criteria passed
No hardcoded secrets
No fake success
Architecture still matches docs/plans/Master_Plan.md
```

Extra checks:

- Confirm the backend can start without Supabase, Qdrant, or ShopAIKey variables.
- Confirm frontend code does not reference backend-only secret names.
- Confirm `SINGLE_USER_ID` is present only in backend configuration.
