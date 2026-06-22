# RagDocument

RagDocument is a personal, single-user document Retrieval-Augmented Generation (RAG) application. It features a robust Python FastAPI backend leveraging LangGraph for orchestration, Supabase for file storage and metadata, Qdrant as a vector database, ShopAIKey for language models, and Jina AI for state-of-the-art reranking. The UI is built using React, Vite, and TypeScript.

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Key Features](#key-features)
3. [Technology Stack](#technology-stack)
4. [Database Schema](#database-schema)
5. [Directory Structure](#directory-structure)
6. [Configuration & Environment Variables](#configuration--environment-variables)
7. [Installation & Setup](#installation--setup)
8. [Testing & Verification](#testing--verification)

---

## System Architecture

RagDocument utilizes **LangGraph** to model stateful multi-step pipelines for document ingestion and retrieval queries.

### 1. Ingestion Pipeline
When a document is uploaded, it transitions through the ingestion graph to process raw content into vector embeddings.

```mermaid
graph TD
    A[Start Ingestion] --> B[Load Document from Supabase]
    B --> C[Set Status to 'processing']
    C --> D[Fetch & Parse Original File]
    D --> E{Determine Strategy}
    E -->|smart_section| F[Smart Heading Scoring & Table Preservation]
    E -->|fixed_token| G[Fixed-Token Splitting]
    F --> H[Save Chunks to Supabase]
    G --> H
    H --> I[Generate Section & Document Summaries]
    I --> J[Generate Embeddings via ShopAIKey]
    J --> K[Upsert Vector & Section Metadata to Qdrant]
    K --> R[Update Lightweight Document Relations]
    R --> S[Set Status to 'ready']
    S --> L[Finish]
    
    subgraph Error Handling
        D -->|Fatal Error| M[Set Status to 'failed']
        F -->|Fatal Error| M
        I -->|Fatal Error| M
        J -->|Fatal Error| M
        K -->|Fatal Error| M
        R -->|Nonfatal Warning| S
        M --> L
    end
```

### 2. Retrieval & Query Pipeline
When a user asks a question, the query workflow creates a bounded typed plan, routes each subquery through its allowed retrieval paths, merges the candidates, applies independent candidate and reranking caps, and continues through token-budgeted context selection and generation.

```mermaid
graph TD
    A[User Prompt / Question] --> B[Validate Question]
    B --> C[Create Bounded Query Plan]
    C --> D[Resolve One-Hop Relation Scope]
    D --> E[Route Semantic, Keyword, Hybrid, Metadata, or Relation Subqueries]
    E --> F[Merge and Cap Candidates by Chunk ID]
    F --> G{Jina Rerank Enabled?}
    G -->|Yes| H[Rerank Chunks via Jina API]
    G -->|No / Fallback| I[Use Deterministic Fusion, Path Score, and Chunk-ID Order]
    H --> J[Filter & Limit to Top-N Chunks]
    I --> J
    J --> K[Select Ranked, Boundary, Same-Section, then Generic Neighbor Chunks]
    K --> L[Deduplicate & Enforce Candidate and Token Budgets]
    L --> M[Generate Answer with Prompt-Local Citation Keys]
    M --> N[Validate Citations Against Exact Context Chunks]
    N --> O[Verify Grounding Against Cited Chunk Text]
    O --> Q{Citation and Grounding Gates Pass?}
    Q -->|No, first failure| R[Regenerate Once with Compact Verifier Feedback]
    R --> N
    Q -->|No, exhausted or provider failure| S[Return Safe Response with No Sources]
    Q -->|Yes| T{Save Message Enabled?}
    T -->|Yes| U[Save Verified Q&A Row to Supabase Messages Table]
    T -->|No| P[Return Response to Client]
    U --> P
    S --> P
```

---

## Key Features

### Backend Capabilities
- **FastAPI Core**: A typed settings layer managed via Pydantic and secured through optional `X-Admin-API-Token` validation (configured on demand via `ADMIN_API_TOKEN`).
- **Unified Document Parsing**: Normalized parser registry ([backend/app/parsing/](file:///C:/Users/ACER/OtherProjects/DocumentAgent/backend/app/parsing)) supporting PDF, DOCX, TXT, Markdown, and HTML format parsing. The parser extracts hierarchical structures such as headings, paragraphs, bullet lists, blockquotes, code, and tables.
- **Smart Section Chunking**: Dynamic, structural chunking strategy ([backend/app/chunking/](file:///C:/Users/ACER/OtherProjects/DocumentAgent/backend/app/chunking)) utilizing deterministic heading scoring to preserve section hierarchies and keep tables intact, falling back to fixed-token boundaries only when structural components exceed length limits.
- **Section-Aware Retrieval**: Context retrieval selects final ranked chunks first, then requested boundary chunks, exact same-section neighbors, and generic same-document neighbors (`RETRIEVAL_CONTEXT_MODE=section_aware`), while enforcing candidate and token budgets and preserving prompt-only truncation for oversized top chunks.
- **Metadata-Aware Hybrid Retrieval**: Chat requests can filter by document allow-list, MIME type, heading, section path, and page range; semantic Qdrant retrieval and Postgres full-text keyword retrieval run independently, recover from single-path failures, and merge candidates with deterministic reciprocal-rank fusion.
- **Bounded Candidate Stages and Reranking**: Retrieval enforces per-path, fused, rerank-candidate, final-reranked, and context-stage caps independently. Jina receives only the configured rerank candidate window, and disabled or invalid reranking falls back deterministically by fusion score, path scores, and chunk ID.
- **Bounded Query Planning and Routing**: The query graph normalizes and caps planned subqueries, preserves explicit document scope and filter precedence, routes semantic, keyword, hybrid, metadata, and one-hop relation strategies only through approved paths, and merges candidates while retaining subquery coverage.
- **Exact Citations and Grounding Gate**: Generated answers use prompt-local `S1`, `S2`, and later citation keys that map back to exact context chunk IDs. Returned sources are limited to cited chunks, factual answers must pass citation validation plus grounding verification against cited chunk text, and failed verification returns a safe no-source response after at most one regeneration.
- **RAG Evaluation Harness**: A versioned text-only evaluation corpus, deterministic fixture validator, production-query evaluation runner, timestamped JSON reports, and CLI quality gates measure retrieval recall/precision, rerank lift, no-result rates, citation validity, grounding pass rate, and answer term quality.
- **Deduplication & Validation**: Deterministic SHA-256 upload hashing prevent duplicate storage and indexing of identical documents.
- **Message History API**: Fast lookups for chat history from the `messages` table with bounded retrieval and failure isolation.
- **Phase 3 Contract Foundation**: Typed retrieval filters, planning/candidate/grounding/citation contracts, compact LangGraph state fields, and bounded Phase 3 settings are available for later advanced RAG batches.
- **Document Summaries**: Ingestion can generate extracted-text-only section and document summaries, store exact source chunk IDs, replace summaries atomically after complete generation, and expose typed `GET /api/documents/{document_id}/summaries` inspection.
- **Lightweight Document Relations**: Ingestion can build bounded, evidence-backed, canonical document relations from summary embedding search, keep relation failures nonfatal to valid indexing, and expose typed `GET /api/documents/{document_id}/relations` inspection with normalized related document IDs.
- **Phase 3 Persistence Foundation**: Idempotent SQL and lazy Supabase services provide document summaries, canonical document relations, and best-effort workflow trace storage.

### Frontend Capabilities
- **React Vite TypeScript Frontend**: Quick build time and typed API integrations. Secret keys remain strictly on the server-side.
- **Document Management Console**: Browser UI for file upload, list status polling, details inspection, reindexing, and full deletion cleanups (removes from database, storage bucket, and vector store).
- **Advanced Chat Interface**:
  - Selection of target documents for focused queries.
  - Collapsible retrieval filters for MIME/file type, heading, section path, and page range, with invalid page ranges blocked before send.
  - Contextual citation rendering (both page-present e.g., `[Doc, p. 3]` and page-absent e.g., `[Doc]` styles).
  - Optional retrieval metadata display for fusion score, retrieval paths, and citation key when available.
  - Multi-chunk navigation drawer (browse preceding or succeeding adjacent source chunks directly in the browser).
  - Single-click restore of old messages and sources into the active chat session without needing to hit the LLM again.

---

## Technology Stack

- **Backend Framework**: Python 3.12, FastAPI, Uvicorn, Pydantic v2
- **Orchestration**: LangGraph, LangChain Community
- **Primary Database (Relational & Blob)**: Supabase (PostgreSQL & Storage Bucket)
- **Vector Database**: Qdrant
- **LLM & Embeddings Provider**: ShopAIKey API (`gpt-4o-mini`, `text-embedding-3-small`)
- **Reranker API**: Jina AI (`jina-reranker-v2-base-multilingual`)
- **Frontend Framework**: React 18, Vite, TypeScript, Vanilla CSS

---

## Database Schema

Applied database definitions are tracked in [docs/database/supabase_schema.sql](file:///C:/Users/ACER/OtherProjects/DocumentAgent/docs/database/supabase_schema.sql):

### 1. `documents` Table
Tracks global status, file characteristics, and parsing configuration.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid` (PK) | Unique document identifier. |
| `title` | `text` | Document title (defaults to file name). |
| `file_name` | `text` | Raw uploaded file name. |
| `mime_type` | `text` | Detected MIME type (e.g., `application/pdf`, `text/html`). |
| `file_size` | `bigint` | Byte size of the file. |
| `file_hash` | `text` (Unique) | SHA-256 hash of file content. |
| `storage_path` | `text` | Reference to the file in Supabase Storage. |
| `status` | `text` | `uploaded`, `processing`, `ready`, or `failed`. |
| `total_pages` | `int` | Total pages in the document. |
| `total_chunks` | `int` | Number of chunks generated. |
| `parser_name` | `text` | Parser engine used. |
| `chunking_strategy` | `text` | Configured chunking type (e.g., `smart_section`). |
| `qdrant_collection` | `text` | The Qdrant collection vectors are saved to. |
| `error_message` | `text` | Capture of fatal ingestion exception details. |
| `error_code` | `text` | Stable optional failure code for migrated Phase 3 ingestion errors. |

### 2. `document_chunks` Table
Stores parsed texts and layout metadata.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid` (PK) | Unique chunk ID. |
| `document_id` | `uuid` (FK) | Reference to `documents.id` (on delete cascade). |
| `chunk_index` | `int` | Sequential chunk index. |
| `content` | `text` | Raw textual content. |
| `token_count` | `int` | Computed token length. |
| `heading` | `text` | Section heading the chunk belongs to. |
| `section_path` | `jsonb` | JSON list of parent headings leading to the chunk. |
| `page_start` / `page_end` | `int` | Page coverage details. |
| `qdrant_point_id` | `text` | Link to the corresponding point in Qdrant. |

### 3. `messages` Table
Maintains historical interactions.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | `uuid` (PK) | Message ID. |
| `question` | `text` | Question queried by the user. |
| `answer` | `text` | Synthesized grounded answer. |
| `sources` | `jsonb` | References array including headers, page ranges, and previews. |
| `metadata` | `jsonb` | Runtime configurations and retrieval metrics. |

### 4. Phase 3 Persistence Tables
Phase 3 adds compact derived-data and workflow telemetry storage:

| Table | Purpose |
| :--- | :--- |
| `document_summaries` | Stores one document summary per document and section summaries keyed by section path. |
| `document_relations` | Stores canonical, non-self document pairs with relation type, evidence chunk IDs, confidence, and model metadata. |
| `workflow_runs` | Stores ingestion/query workflow status, compact trace events, error codes, and timing metadata. |

### 5. Phase 3 Keyword Retrieval SQL
Phase 3 SQL also defines a language-neutral Postgres full-text GIN index over chunk heading/content and the `search_document_chunks_keyword` RPC. This RPC applies the same document, MIME, heading, section path, and page-overlap filters used by semantic retrieval, then returns deterministic keyword candidates for hybrid fusion.

---

## Directory Structure

```
RagDocument/
├── backend/
│   ├── app/
│   │   ├── api/             # API Router definitions (/health, /documents, /chat, /messages)
│   │   ├── chunking/        # Heading scoring and smart-section chunkers
│   │   ├── core/            # Configuration setting loader (Pydantic Settings)
│   │   ├── evaluation/      # Versioned RAG evaluation dataset, metrics, and runner
│   │   ├── graphs/          # LangGraph ingestion and query workflow graphs
│   │   ├── models/          # SQLAlchemy or Pydantic models
│   │   ├── parsing/         # Extensible document parsers (PDF, DOCX, TXT, MD, HTML)
│   │   ├── services/        # Lazy-initialization factories for DB & third-party services
│   │   └── main.py          # FastAPI application entry point
│   ├── tests/               # pytest test cases covering graphs, chunkers, and APIs
│   ├── evaluation/          # Text-only evaluation fixtures, datasets, and ignored result reports
│   ├── pyproject.toml
│   └── README.md            # Backend environment and local activation guides
├── docs/
│   └── database/
│       └── supabase_schema.sql  # SQL schema migrations
├── frontend/
│   ├── src/
│   │   ├── api/             # Frontend client communicating with API routes
│   │   ├── components/      # UI components (Chat, Upload, History)
│   │   ├── App.tsx          # Main React Application
│   │   └── styles.css       # Core styling definitions
│   ├── tsconfig.json
│   └── vite.config.ts
└── README.md                # Root project entry point
```

---

## Configuration & Environment Variables

Create a file named `.env` in the `backend/` subdirectory.

```env
APP_ENV=development
FRONTEND_ORIGIN=http://localhost:5173
ADMIN_API_TOKEN=your-random-token-here

# Supabase Credentials
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_STORAGE_BUCKET=documents

# ShopAIKey Config
SHOPAIKEY_API_KEY=your-shopaikey-token
SHOPAIKEY_BASE_URL=https://api.shopaikey.com/v1
SHOPAIKEY_CHAT_MODEL=gpt-4o-mini
SHOPAIKEY_EMBEDDING_MODEL=text-embedding-3-small

# Qdrant Database Config
QDRANT_URL=https://your-cluster-url.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION=document_chunks_v1

# Reranker Options
ENABLE_RERANK=true
JINA_API_KEY=your-jina-token
JINA_RERANK_MODEL=jina-reranker-v2-base-multilingual

# Ingestion & Chunking parameters
CHUNKING_STRATEGY=smart_section
HEADER_SCORE_THRESHOLD=4
TABLE_CHUNK_MAX_TOKENS=500
CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=150

# Retrieval & Search parameters
RETRIEVAL_SEMANTIC_TOP_K=40
RETRIEVAL_FINAL_TOP_K=5
RETRIEVAL_CONTEXT_MODE=section_aware
RETRIEVAL_SECTION_SIBLING_WINDOW=1
RETRIEVAL_CONTEXT_WINDOW=1
RETRIEVAL_CONTEXT_MAX_CANDIDATES=8

# Phase 3 retrieval, planning, summaries, relations, grounding, and tracing
ENABLE_KEYWORD_SEARCH=true
RETRIEVAL_KEYWORD_TOP_K=40
RETRIEVAL_FUSION_TOP_K=40
RETRIEVAL_RRF_CONSTANT=60
RETRIEVAL_RERANK_CANDIDATE_TOP_K=20
RETRIEVAL_CONTEXT_MAX_TOKENS=4000
QUERY_MAX_SUBQUERIES=4
QUERY_PLANNER_TEMPERATURE=0.0
QUERY_PLANNER_MAX_TOKENS=500
ENABLE_SUMMARIES=true
SUMMARY_SECTION_MAX_TOKENS=200
SUMMARY_DOCUMENT_MAX_TOKENS=400
ENABLE_RELATION_RETRIEVAL=true
RELATION_MAX_RELATED_DOCUMENTS=5
GROUNDING_MIN_SCORE=0.80
GROUNDING_MAX_REGENERATIONS=1
WORKFLOW_MAX_ATTEMPTS=3
WORKFLOW_RETRY_BASE_DELAY_SECONDS=0.25
WORKFLOW_RETRY_MAX_DELAY_SECONDS=2.0
ENABLE_WORKFLOW_TRACING=true

# LLM Generation Parameters
TEMPERATURE=0.2
MAX_OUTPUT_TOKENS=1200
MAX_UPLOAD_BYTES=25000000
```

---

## Installation & Setup

### Prerequisite External Resources
1. **Supabase Database**: Execute the contents of [docs/database/supabase_schema.sql](file:///C:/Users/ACER/OtherProjects/DocumentAgent/docs/database/supabase_schema.sql) in your project's SQL editor.
   - Existing Phase 2 databases can apply [docs/database/phase3_migration.sql](file:///C:/Users/ACER/OtherProjects/DocumentAgent/docs/database/phase3_migration.sql) to add the Phase 3 column, persistence tables, keyword-search index, and keyword RPC when authorized for manual migration.
2. **Supabase Bucket**: Create a private storage bucket named `documents` (or matching `SUPABASE_STORAGE_BUCKET`).
3. **Qdrant Collection**: Initialize a collection named `document_chunks_v1` (matching `QDRANT_COLLECTION`). Ensure the vector size matches your embedding model's dimensions (1532 for `text-embedding-3-small` or standard default).

### Backend Launch
Run the backend with Python 3.12 from the root folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend Launch
Launch the React application:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Ensure `FRONTEND_ORIGIN` in your backend `.env` matches the frontend deployment address (`http://127.0.0.1:5173` or `http://localhost:5173`) to satisfy CORS configurations.

---

## Testing & Verification

Verify API functionality and parsing algorithms.

### 1. Run Backend Tests
Execute pytest across the suite:
```powershell
cd backend
python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_api_messages.py tests/test_parsers.py tests/test_heading_detection.py tests/test_chunker.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_api_chat.py -v
python -m pytest tests/test_contracts.py tests/test_keyword_search.py tests/test_score_fusion.py tests/test_retrieval_context.py tests/test_query_planning.py tests/test_summaries.py tests/test_relations.py tests/test_observability.py -v
python -m pytest tests/test_evaluation_metrics.py -v
python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl
python scripts/run_rag_evaluation.py --help
```

### 2. Run Frontend Build Check
Ensure TypeScript checks and compilation compile smoothly:
```powershell
cd frontend
npm run build
```
