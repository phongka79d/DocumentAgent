# RagDocument

RagDocument Phase 1 is a personal, single-user document RAG MVP.

This repository is currently at Batch01, the backend foundation only. The accepted Batch01 behavior is:

- a FastAPI backend titled `RagDocument API`
- `GET /api/health` returning `{"status": "ok"}`
- a typed settings layer in `backend/app/core/config.py`
- CORS configured from `FRONTEND_ORIGIN`
- an optional `X-Admin-API-Token` gate that is disabled when `ADMIN_API_TOKEN` is empty and enforced when it is set

The current backend uses safe local-development defaults for its settings layer. It does not implement upload, indexing, retrieval, chat, frontend UI, external service clients, or end-to-end workflow validation yet.

## Validation

Run the Batch01 backend config checks with:

```bash
cd backend
python -m pytest tests/test_config.py -v
```
