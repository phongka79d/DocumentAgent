# Document QA Agent Implementation Plans

These files split `docs/Plan.md` into independent implementation milestones. Each plan is intended to be implemented, tested, reviewed, and accepted before the next plan starts.

Architecture decisions preserved across the sequence: no Auth/JWT in the MVP, `SINGLE_USER_ID` ownership, Supabase Service Role Key backend-only, Qdrant Cloud as the only VectorDB, ShopAIKey for chat completion and embeddings, PDF/DOCX/TXT/CSV support, medium GraphRAG, three-agent QA, verified chunks only for final answers, and file name plus quote citations.

## Plan Order

1. [Plan_1.md](Plan_1.md) - Project Foundation
   - Completes the backend FastAPI skeleton, frontend React skeleton, shared project structure, config loading, and health check.
   - Test after completion: backend starts, frontend builds, and `GET /api/health` returns a valid response.

2. [Plan_2.md](Plan_2.md) - Database Schema and Supabase Setup
   - Completes Supabase PostgreSQL schema, storage bucket assumptions, service-role backend client, and connection checks.
   - Test after completion: migrations are runnable, required tables exist, and backend can connect to Supabase without exposing secrets.

3. [Plan_3.md](Plan_3.md) - Document Upload and Metadata
   - Completes document upload, file validation, Supabase Storage upload, document metadata insert, document list, and document detail APIs.
   - Test after completion: supported files upload, unsupported files fail with HTTP 400, and documents are listed for `SINGLE_USER_ID`.

4. [Plan_4.md](Plan_4.md) - Document Parsing and Chunking
   - Completes PDF, DOCX, TXT, and CSV parsing plus recursive chunking and chunk persistence.
   - Test after completion: each supported file type produces persisted chunks with correct metadata and empty documents fail clearly.

5. [Plan_5.md](Plan_5.md) - ShopAIKey Embeddings and Qdrant Indexing
   - Completes embedding generation, Qdrant collection creation, vector upsert, payload format, and chunk point ID updates.
   - Test after completion: chunks can be embedded, indexed, and found in Qdrant by vector search.

6. [Plan_6.md](Plan_6.md) - Basic Semantic Retrieval
   - Completes question embedding, Qdrant semantic search, Top-K configuration, and `/api/retrieval/search`.
   - Test after completion: a question returns scored semantic chunk results filtered by user and selected documents.

7. [Plan_7.md](Plan_7.md) - Medium GraphRAG Data Model and Graph Builder
   - Completes entity extraction, entity persistence, relationship persistence, and document-section-chunk-entity graph building.
   - Test after completion: graph records are generated for chunks and can support graph expansion.

8. [Plan_8.md](Plan_8.md) - Hybrid Retrieval and Scoring
   - Completes semantic and graph candidate merge, score normalization, scoring formula, optional rerank placeholder, and final Top-K selection.
   - Test after completion: hybrid retrieval returns sorted candidates with every score component populated.

9. [Plan_9.md](Plan_9.md) - Agent 1 Retrieval Agent
   - Completes Agent 1 schema, retrieval orchestration, structured output, and agent-step logging.
   - Test after completion: Agent 1 returns candidate chunks and logs retrieval inputs, outputs, and scores.

10. [Plan_10.md](Plan_10.md) - Agent 2 Evidence Verification Agent
    - Completes evidence verification prompt, structured validation, contradiction checks, verified and rejected chunk output, and logging.
    - Test after completion: Agent 2 accepts useful chunks, rejects weak chunks, sets `missing_information`, and reports confidence.

11. [Plan_11.md](Plan_11.md) - Agent 3 Answer Generation and Self-Check Agent
    - Completes grounded answer generation, citation formatting, insufficient-evidence handling, self-check, and logging.
    - Test after completion: answers use verified chunks only and include file-name plus quote citations.

12. [Plan_12.md](Plan_12.md) - LangGraph Full QA Workflow
    - Completes the full LangGraph workflow, `/api/chat/ask`, agent run persistence, agent step persistence, evidence API, and logs API.
    - Test after completion: one API request runs Agent 1, Agent 2, Agent 3, self-check, persistence, and returns a final answer.

13. [Plan_13.md](Plan_13.md) - Frontend Upload and Document List
    - Completes frontend API client, upload page, document list page, progress display, status display, and error states.
    - Test after completion: user can upload documents and see processing status in the browser.

14. [Plan_14.md](Plan_14.md) - Frontend Chat and Evidence Viewer
    - Completes chat UI, document selector, answer display, confidence display, citations, verified evidence, and rejected evidence.
    - Test after completion: user can ask questions and inspect the evidence behind each answer.

15. [Plan_15.md](Plan_15.md) - Agent Logs Debug UI
    - Completes agent logs page, run selection, step viewer, raw JSON display, retrieval scores, verification results, and self-check output.
    - Test after completion: developer can inspect a full agent run from the frontend.

16. [Plan_16.md](Plan_16.md) - End-to-End Testing and Stabilization
    - Completes upload-to-answer regression testing, sample documents, bug fixes, final documentation, and MVP acceptance checks.
    - Test after completion: the complete document QA flow answers the sample Vietnamese question with grounded citations.
