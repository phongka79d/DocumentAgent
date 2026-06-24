# Backend Behavior-Preserving Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend into smaller, safer modules while preserving API behavior, graph behavior, public import compatibility, and the passing test suite; also make `backend/.env.example` the single user-facing environment contract.

**Architecture:** Use a strangler refactor: keep current public modules as compatibility facades, move focused internals behind them, and verify every phase with characterization tests plus the full backend suite. The only approved behavior change is configuration documentation/contract cleanup: active docs point to one canonical env file instead of duplicating env blocks.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Pydantic Settings, LangGraph, Supabase, Qdrant, ShopAIKey/OpenAI-compatible client, Jina rerank client, pytest.

---

## Non-negotiable constraints

- Do not edit `backend/.env`.
- Do not change endpoint paths, request schemas, response schemas, status codes, or current synchronous indexing/chat behavior.
- Do not remove these public import surfaces during this refactor:
  - `app.graphs.query_nodes`
  - `app.graphs.ingestion_nodes`
  - `app.services.retrieval`
  - `app.models.schemas`
  - `app.graphs.query_prompts`
  - `app.graphs.query_formatting`
- Preserve monkeypatch compatibility used by existing tests. If a test patches `query_nodes.generate_answer_node`, `ingestion_nodes.create_supabase_client`, or `retrieval.embed_question`, the patched value must still affect the tested path.
- Every task must end with targeted tests and `python -m pytest -q` from `backend/`.
- If a suspected bug is found while moving code, document it in the task notes and keep behavior unchanged unless the task explicitly covers the approved env-contract change.

## Target file structure

### Create

- `backend/.env.example` — canonical user-facing env contract.
- `backend/app/rag/__init__.py` — RAG helper package marker.
- `backend/app/rag/prompts.py` — answer, planning, grounding, and regeneration prompts.
- `backend/app/rag/formatting.py` — context prompt, source citation, chat response parsing, and message metadata helpers.
- `backend/app/graphs/query_steps/__init__.py` — query step package marker.
- `backend/app/graphs/query_steps/dependencies.py` — dependency object used by moved query step implementations.
- `backend/app/graphs/query_steps/prepare.py` — query preparation and filter normalization.
- `backend/app/graphs/query_steps/planning.py` — query planning and relation-scope node implementation.
- `backend/app/graphs/query_steps/retrieval.py` — candidate retrieval, fusion, rerank, and context expansion node implementation.
- `backend/app/graphs/query_steps/answering.py` — answer generation and regeneration node implementation.
- `backend/app/graphs/query_steps/verification.py` — citation validation, grounding verification, and finalize node implementation.
- `backend/app/graphs/query_steps/persistence.py` — optional message persistence node implementation.
- `backend/app/graphs/ingestion_steps/__init__.py` — ingestion step package marker.
- `backend/app/graphs/ingestion_steps/dependencies.py` — dependency object used by moved ingestion step implementations.
- `backend/app/graphs/ingestion_steps/records.py` — load document and mark processing nodes.
- `backend/app/graphs/ingestion_steps/parsing.py` — parse document node.
- `backend/app/graphs/ingestion_steps/chunking.py` — chunk document node.
- `backend/app/graphs/ingestion_steps/persistence.py` — save chunks node.
- `backend/app/graphs/ingestion_steps/summaries.py` — summarize document node.
- `backend/app/graphs/ingestion_steps/indexing.py` — embed chunks and upsert Qdrant nodes.
- `backend/app/graphs/ingestion_steps/relations.py` — update document relations node.
- `backend/app/graphs/ingestion_steps/finalization.py` — mark ready and mark failed nodes.
- `backend/app/services/retrieval_normalization.py` — retrieval row, payload, score, UUID, and text normalization helpers.
- `backend/app/services/retrieval_filters.py` — Qdrant filter construction.
- `backend/app/services/semantic_retrieval.py` — embedding and Qdrant semantic search implementation.
- `backend/app/services/reranking.py` — Jina rerank implementation.

### Modify

- `backend/app/core/config.py` — keep typed settings, remove misleading placeholder service defaults where safe, and keep validation centralized.
- `backend/tests/test_config.py` — add env-example contract tests and update active-doc tests.
- `README.md` — remove inline backend env block; point to `backend/.env.example`.
- `backend/README.md` — remove inline backend env block; point to `backend/.env.example`.
- `backend/app/graphs/query_prompts.py` — compatibility re-export from `app.rag.prompts`.
- `backend/app/graphs/query_formatting.py` — compatibility re-export from `app.rag.formatting`.
- `backend/app/services/query_planning.py` — import prompts from `app.rag.prompts`.
- `backend/app/services/grounding.py` — import prompts from `app.rag.prompts`.
- `backend/app/services/citation_validation.py` — import formatting from `app.rag.formatting`.
- `backend/app/graphs/query_nodes.py` — convert to compatibility facade with wrappers that call `query_steps`.
- `backend/app/graphs/ingestion_nodes.py` — convert to compatibility facade with wrappers that call `ingestion_steps`.
- `backend/app/services/retrieval.py` — convert to compatibility facade while preserving existing exported names.
- `backend/tests/test_query_graph.py` — add import-surface and monkeypatch-compatibility characterization tests before moving query nodes.
- `backend/tests/test_ingestion_graph.py` — add import-surface and monkeypatch-compatibility characterization tests before moving ingestion nodes.
- `backend/tests/test_score_fusion.py` — add retrieval facade characterization around monkeypatched semantic search helpers.

---

## Task 1: Establish baseline and canonical env contract

**Files:**
- Create: `backend/.env.example`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_config.py`
- Modify: `README.md`
- Modify: `backend/README.md`

- [x] **Step 1: Run baseline backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
340 passed
```

- [x] **Step 2: Add the canonical env example file**

Create `backend/.env.example` with this exact content:

```env
APP_ENV=development
FRONTEND_ORIGIN=http://localhost:5173
ADMIN_API_TOKEN=

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_STORAGE_BUCKET=documents

SHOPAIKEY_API_KEY=your-shopaikey-token
SHOPAIKEY_BASE_URL=https://api.shopaikey.com/v1
SHOPAIKEY_CHAT_MODEL=gpt-5-mini
SHOPAIKEY_INPUT_MODEL=gpt-5-mini
SHOPAIKEY_EMBEDDING_MODEL=text-embedding-3-small

QDRANT_URL=https://your-cluster-url.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION=document_chunks_v1

ENABLE_RERANK=true
ENABLE_KEYWORD_SEARCH=true
ENABLE_SUMMARIES=true
ENABLE_RELATION_RETRIEVAL=true
ENABLE_WORKFLOW_TRACING=true
JINA_API_KEY=your-jina-token
JINA_RERANK_MODEL=jina-reranker-v2-base-multilingual

RETRIEVAL_SEMANTIC_TOP_K=40
RETRIEVAL_FINAL_TOP_K=5
RETRIEVAL_CONTEXT_MODE=section_aware
RETRIEVAL_CONTEXT_WINDOW=1
RETRIEVAL_SECTION_SIBLING_WINDOW=1
RETRIEVAL_CONTEXT_MAX_CANDIDATES=8
RETRIEVAL_HINT_TEMPERATURE=0.0
RETRIEVAL_HINT_MAX_TOKENS=120
RETRIEVAL_BOUNDARY_START_CHUNKS=2
RETRIEVAL_BOUNDARY_END_CHUNKS=2
RETRIEVAL_KEYWORD_TOP_K=40
RETRIEVAL_FUSION_TOP_K=40
RETRIEVAL_RRF_CONSTANT=60
RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K=5
RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K=2
RETRIEVAL_RERANK_FUSED_TOP_K=10
RETRIEVAL_RERANK_CANDIDATE_TOP_K=40
RETRIEVAL_CONTEXT_MAX_TOKENS=4000

QUERY_MAX_SUBQUERIES=4
QUERY_PLANNER_TEMPERATURE=0.0
QUERY_PLANNER_MAX_TOKENS=500

SUMMARY_SECTION_MAX_TOKENS=200
SUMMARY_DOCUMENT_MAX_TOKENS=400
RELATION_MAX_RELATED_DOCUMENTS=5
GROUNDING_MIN_SCORE=0.80
GROUNDING_MAX_REGENERATIONS=1

WORKFLOW_MAX_ATTEMPTS=3
WORKFLOW_RETRY_BASE_DELAY_SECONDS=0.25
WORKFLOW_RETRY_MAX_DELAY_SECONDS=2.0

ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP=true

CHUNKING_STRATEGY=smart_section
HEADER_SCORE_THRESHOLD=4
TABLE_CHUNK_MAX_TOKENS=500
CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=150

MAX_UPLOAD_BYTES=25000000
TEMPERATURE=0.2
MAX_OUTPUT_TOKENS=1200
```

- [x] **Step 3: Add env contract tests**

In `backend/tests/test_config.py`, add these helpers after `ALL_SETTINGS_FIELDS`:

```python
ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / ".env.example"
ACTIVE_DOC_PATHS = [
    Path(__file__).resolve().parents[2] / "README.md",
    Path(__file__).resolve().parents[1] / "README.md",
]


def _env_example_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator == "=", f"Invalid env example line: {raw_line}"
        values[key] = value
    return values
```

Then add these tests after `test_settings_load_defaults_from_master_plan`:

```python
def test_env_example_lists_every_settings_field():
    values = _env_example_values()

    assert set(values) == ALL_SETTINGS_FIELDS


def test_active_docs_do_not_duplicate_backend_env_values():
    assignment_names = tuple(sorted(ALL_SETTINGS_FIELDS))
    for path in ACTIVE_DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert not any(
                stripped.startswith(f"{name}=") for name in assignment_names
            ), f"{path} duplicates backend env value line: {stripped}"


def test_service_placeholder_values_live_only_in_env_example():
    settings = Settings(_env_file=None)

    assert settings.SUPABASE_URL == ""
    assert settings.SUPABASE_SERVICE_ROLE_KEY == ""
    assert settings.SHOPAIKEY_API_KEY == ""
    assert settings.QDRANT_URL == ""
    assert settings.QDRANT_API_KEY == ""
    assert settings.JINA_API_KEY == ""
```

- [x] **Step 4: Run env contract tests and confirm they fail before implementation**

Run from `backend/`:

```powershell
python -m pytest tests/test_config.py::test_env_example_lists_every_settings_field tests/test_config.py::test_active_docs_do_not_duplicate_backend_env_values tests/test_config.py::test_service_placeholder_values_live_only_in_env_example -q
```

Expected before implementation:

```text
FAILED
```

- [x] **Step 5: Update settings service-placeholder defaults**

In `backend/app/core/config.py`, change only external service credential defaults to empty strings:

```python
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "documents"

    SHOPAIKEY_API_KEY: str = ""
    SHOPAIKEY_BASE_URL: str = "https://api.shopaikey.com/v1"
    SHOPAIKEY_CHAT_MODEL: str = "gpt-5-mini"
    SHOPAIKEY_INPUT_MODEL: str = "gpt-5-mini"
    SHOPAIKEY_EMBEDDING_MODEL: str = "text-embedding-3-small"

    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "document_chunks_v1"

    ENABLE_RERANK: bool = True
```

And update `JINA_API_KEY`:

```python
    JINA_API_KEY: str = ""
```

- [x] **Step 6: Update existing default assertions**

In `backend/tests/test_config.py`, update existing assertions in `test_settings_load_defaults_from_master_plan`:

```python
    assert settings.SUPABASE_URL == ""
    assert settings.SUPABASE_SERVICE_ROLE_KEY == ""
    assert settings.SHOPAIKEY_API_KEY == ""
    assert settings.SHOPAIKEY_CHAT_MODEL == "gpt-5-mini"
    assert settings.SHOPAIKEY_INPUT_MODEL == "gpt-5-mini"
    assert settings.QDRANT_URL == ""
    assert settings.QDRANT_API_KEY == ""
    assert settings.JINA_API_KEY == ""
```

- [x] **Step 7: Remove inline env blocks from active docs**

In `README.md`, replace the backend env block with:

```markdown
Copy `backend/.env.example` to `backend/.env`, then replace the service placeholders with your Supabase, Qdrant, ShopAIKey, and Jina values. `backend/.env.example` is the single active reference for backend environment variables.
```

In `backend/README.md`, replace the backend env block and variable tables with:

```markdown
Copy `.env.example` to `.env`, then replace the service placeholders with your own values. `.env.example` is the single active reference for backend environment variables; this README intentionally does not duplicate those values.
```

- [x] **Step 8: Run config tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_config.py -q
```

Expected:

```text
passed
```

- [x] **Step 9: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 10: Commit task**

Run from repository root:

```powershell
git add backend/.env.example backend/app/core/config.py backend/tests/test_config.py README.md backend/README.md
git commit -m "refactor: centralize backend env example"
```

---

## Task 2: Add import and monkeypatch compatibility characterization

**Files:**
- Modify: `backend/tests/test_query_graph.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_score_fusion.py`

- [x] **Step 1: Add query node public surface test**

In `backend/tests/test_query_graph.py`, add:

```python
def test_query_nodes_public_surface_remains_available():
    public_names = {
        "prepare_query_node",
        "plan_query_node",
        "resolve_relation_scope_node",
        "retrieve_candidates_node",
        "fuse_candidates_node",
        "rerank_candidates_node",
        "expand_context_node",
        "generate_answer_node",
        "regenerate_answer_node",
        "validate_citations_node",
        "verify_grounding_node",
        "finalize_answer_node",
        "save_message_optional_node",
        "retrieve_qdrant_node",
        "jina_rerank_node",
        "expand_neighbor_context_node",
    }

    for name in public_names:
        assert callable(getattr(query_nodes, name))
```

- [x] **Step 2: Add ingestion node public surface test**

In `backend/tests/test_ingestion_graph.py`, add:

```python
def test_ingestion_nodes_public_surface_remains_available():
    public_names = {
        "load_document_record_node",
        "mark_processing_node",
        "parse_document_node",
        "chunk_document_node",
        "save_chunks_node",
        "summarize_document_node",
        "embed_chunks_node",
        "upsert_qdrant_node",
        "update_document_relations_node",
        "mark_ready_node",
        "mark_failed_node",
    }

    for name in public_names:
        assert callable(getattr(ingestion_nodes, name))
```

- [x] **Step 3: Add retrieval public surface test**

In `backend/tests/test_score_fusion.py`, add:

```python
def test_retrieval_public_surface_remains_available():
    public_names = {
        "embed_question",
        "search_semantic_chunks",
        "retrieve_semantic_candidates",
        "retrieve_hybrid_chunks",
        "rerank_chunks",
        "retrieve_context_chunks",
    }

    for name in public_names:
        assert callable(getattr(retrieval, name))
```

- [x] **Step 4: Run characterization tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py::test_query_nodes_public_surface_remains_available tests/test_ingestion_graph.py::test_ingestion_nodes_public_surface_remains_available tests/test_score_fusion.py::test_retrieval_public_surface_remains_available -q
```

Expected:

```text
passed
```

- [x] **Step 5: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 6: Commit task**

Run from repository root:

```powershell
git add backend/tests/test_query_graph.py backend/tests/test_ingestion_graph.py backend/tests/test_score_fusion.py
git commit -m "test: lock backend refactor compatibility surfaces"
```

---

## Task 3: Move RAG prompts and formatting out of graph layer

**Files:**
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/prompts.py`
- Create: `backend/app/rag/formatting.py`
- Modify: `backend/app/graphs/query_prompts.py`
- Modify: `backend/app/graphs/query_formatting.py`
- Modify: `backend/app/services/query_planning.py`
- Modify: `backend/app/services/grounding.py`
- Modify: `backend/app/services/citation_validation.py`

- [x] **Step 1: Copy prompt implementation into `app.rag.prompts`**

Copy the complete current contents of `backend/app/graphs/query_prompts.py` into `backend/app/rag/prompts.py`, changing no function bodies, constants, or `__all__`.

- [x] **Step 2: Copy formatting implementation into `app.rag.formatting`**

Copy the complete current contents of `backend/app/graphs/query_formatting.py` into `backend/app/rag/formatting.py`, changing no function bodies, constants, or `__all__`.

- [x] **Step 3: Replace old prompt module with compatibility re-export**

Replace `backend/app/graphs/query_prompts.py` with:

```python
from __future__ import annotations

from app.rag.prompts import *  # noqa: F401,F403
from app.rag.prompts import __all__
```

- [x] **Step 4: Replace old formatting module with compatibility re-export**

Replace `backend/app/graphs/query_formatting.py` with:

```python
from __future__ import annotations

from app.rag.formatting import *  # noqa: F401,F403
from app.rag.formatting import __all__
```

- [x] **Step 5: Update service imports**

In these files, replace imports from `app.graphs.query_prompts` or `app.graphs.query_formatting` with imports from `app.rag.prompts` or `app.rag.formatting`:

```text
backend/app/services/query_planning.py
backend/app/services/grounding.py
backend/app/services/citation_validation.py
```

Example replacement:

```python
from app.rag.prompts import build_query_planning_messages
```

Example replacement inside `citation_validation.py`:

```python
from app.rag.formatting import build_source_citations
```

- [x] **Step 6: Run prompt and formatting tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_planning.py tests/test_grounding.py tests/test_query_graph.py -q
```

Expected:

```text
passed
```

- [x] **Step 7: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 8: Commit task**

Run from repository root:

```powershell
git add backend/app/rag backend/app/graphs/query_prompts.py backend/app/graphs/query_formatting.py backend/app/services/query_planning.py backend/app/services/grounding.py backend/app/services/citation_validation.py
git commit -m "refactor: move rag prompts and formatting"
```

---

## Task 4: Split query node implementation behind the existing facade

**Files:**
- Create: `backend/app/graphs/query_steps/__init__.py`
- Create: `backend/app/graphs/query_steps/dependencies.py`
- Create: `backend/app/graphs/query_steps/prepare.py`
- Create: `backend/app/graphs/query_steps/planning.py`
- Create: `backend/app/graphs/query_steps/retrieval.py`
- Create: `backend/app/graphs/query_steps/answering.py`
- Create: `backend/app/graphs/query_steps/verification.py`
- Create: `backend/app/graphs/query_steps/persistence.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Test: `backend/tests/test_query_graph.py`

- [x] **Step 1: Add query step dependency object**

Create `backend/app/graphs/query_steps/dependencies.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueryStepDependencies:
    retrieval: Any
    relations: Any
    grounding: Any
    citation_validation: Any
    message_service: Any
    build_context_prompt: Callable[..., str]
    build_source_citations: Callable[..., list[dict[str, Any]]]
    extract_chat_content: Callable[..., str | None]
    message_metadata: Callable[..., dict[str, Any]]
    create_shopaikey_client: Callable[..., Any]
```

- [x] **Step 2: Move preparation helpers and node**

Move these symbols from `backend/app/graphs/query_nodes.py` to `backend/app/graphs/query_steps/prepare.py`:

```text
_normalize_document_ids
_normalize_retrieval_filters
_normalize_question
prepare_query_node
```

Keep function bodies unchanged. If a helper name differs in the current file, move the exact current helper that serves the same preparation responsibility and keep its name.

- [x] **Step 3: Add facade wrapper for preparation**

In `backend/app/graphs/query_nodes.py`, import the moved implementation and expose the same public function:

```python
from app.graphs.query_steps import prepare as _prepare_steps


def prepare_query_node(state: QueryState, *, settings: Settings | None = None) -> dict[str, Any]:
    return _prepare_steps.prepare_query_node(state, settings=settings)
```

- [x] **Step 4: Run query tests after preparation move**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py -q
```

Expected:

```text
passed
```

- [x] **Step 5: Move planning node implementation**

Move these symbols to `backend/app/graphs/query_steps/planning.py`:

```text
plan_query_node
resolve_relation_scope_node
```

Change the implementation signatures in the moved module to accept dependencies:

```python
def plan_query_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    ...
```

```python
def resolve_relation_scope_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    ...
```

Inside the moved code, replace direct module references such as `relations` with `deps.relations`.

- [x] **Step 6: Add facade dependency factory and planning wrappers**

In `backend/app/graphs/query_nodes.py`, add:

```python
from app.graphs.query_steps.dependencies import QueryStepDependencies


def _query_step_dependencies() -> QueryStepDependencies:
    return QueryStepDependencies(
        retrieval=retrieval,
        relations=relations,
        grounding=grounding,
        citation_validation=citation_validation,
        message_service=message_service,
        build_context_prompt=build_context_prompt,
        build_source_citations=build_source_citations,
        extract_chat_content=extract_chat_content,
        message_metadata=message_metadata,
        create_shopaikey_client=create_shopaikey_client,
    )
```

Then expose wrappers:

```python
def plan_query_node(state: QueryState, *, settings: Settings | None = None) -> dict[str, Any]:
    return _planning_steps.plan_query_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


def resolve_relation_scope_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _planning_steps.resolve_relation_scope_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )
```

- [x] **Step 7: Run query tests after planning move**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_query_planning.py -q
```

Expected:

```text
passed
```

- [x] **Step 8: Move retrieval-phase query nodes**

Move these symbols to `backend/app/graphs/query_steps/retrieval.py`:

```text
retrieve_candidates_node
fuse_candidates_node
rerank_candidates_node
expand_context_node
retrieve_qdrant_node
jina_rerank_node
expand_neighbor_context_node
```

Use `deps.retrieval` for calls that previously used the facade module variable `retrieval`.

- [x] **Step 9: Add retrieval wrappers in the facade**

In `backend/app/graphs/query_nodes.py`, expose wrappers with the existing public names:

```python
def retrieve_candidates_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.retrieve_candidates_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )
```

Repeat the same wrapper pattern for:

```text
fuse_candidates_node
rerank_candidates_node
expand_context_node
retrieve_qdrant_node
jina_rerank_node
expand_neighbor_context_node
```

- [x] **Step 10: Run query retrieval tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_score_fusion.py tests/test_retrieval_context.py -q
```

Expected:

```text
passed
```

- [x] **Step 11: Move answer-generation nodes**

Move these symbols to `backend/app/graphs/query_steps/answering.py`:

```text
generate_answer_node
regenerate_answer_node
```

Use dependency fields for formatting and client creation:

```python
context_prompt = deps.build_context_prompt(context_chunks)
client = deps.create_shopaikey_client(settings=resolved_settings)
answer = deps.extract_chat_content(response)
sources = deps.build_source_citations(context_chunks)
```

- [x] **Step 12: Add answer wrappers in the facade**

In `backend/app/graphs/query_nodes.py`, expose:

```python
def generate_answer_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _answering_steps.generate_answer_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


def regenerate_answer_node(
    state: QueryState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _answering_steps.regenerate_answer_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )
```

- [x] **Step 13: Move verification nodes**

Move these symbols to `backend/app/graphs/query_steps/verification.py`:

```text
validate_citations_node
verify_grounding_node
finalize_answer_node
```

Use `deps.citation_validation` and `deps.grounding` in moved code.

- [x] **Step 14: Move persistence node**

Move `save_message_optional_node` to `backend/app/graphs/query_steps/persistence.py`.

Use `deps.message_service` and `deps.message_metadata` in moved code.

- [x] **Step 15: Add verification and persistence wrappers**

In `backend/app/graphs/query_nodes.py`, expose wrappers for:

```text
validate_citations_node
verify_grounding_node
finalize_answer_node
save_message_optional_node
```

Each wrapper must pass `_query_step_dependencies()` into the moved implementation.

- [x] **Step 16: Preserve facade exports**

At the bottom of `backend/app/graphs/query_nodes.py`, keep all existing `__all__` names. If `__all__` does not exist, add one containing every public node and compatibility alias currently imported by tests.

- [x] **Step 17: Run query tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_api_chat.py tests/test_query_planning.py tests/test_grounding.py tests/test_citation_validation.py -q
```

Expected:

```text
passed
```

- [x] **Step 18: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 19: Commit task**

Run from repository root:

```powershell
git add backend/app/graphs/query_nodes.py backend/app/graphs/query_steps backend/tests/test_query_graph.py
git commit -m "refactor: split query graph node steps"
```

---

## Task 5: Split ingestion node implementation behind the existing facade

**Files:**
- Create: `backend/app/graphs/ingestion_steps/__init__.py`
- Create: `backend/app/graphs/ingestion_steps/dependencies.py`
- Create: `backend/app/graphs/ingestion_steps/records.py`
- Create: `backend/app/graphs/ingestion_steps/parsing.py`
- Create: `backend/app/graphs/ingestion_steps/chunking.py`
- Create: `backend/app/graphs/ingestion_steps/persistence.py`
- Create: `backend/app/graphs/ingestion_steps/summaries.py`
- Create: `backend/app/graphs/ingestion_steps/indexing.py`
- Create: `backend/app/graphs/ingestion_steps/relations.py`
- Create: `backend/app/graphs/ingestion_steps/finalization.py`
- Modify: `backend/app/graphs/ingestion_nodes.py`
- Test: `backend/tests/test_ingestion_graph.py`
- Test: `backend/tests/test_api_documents.py`

- [x] **Step 1: Add ingestion step dependency object**

Create `backend/app/graphs/ingestion_steps/dependencies.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IngestionStepDependencies:
    create_supabase_client: Callable[..., Any]
    create_shopaikey_client: Callable[..., Any]
    create_qdrant_client: Callable[..., Any]
    get_parser_for_file: Callable[..., Any]
    relations: Any
```

- [x] **Step 2: Add facade dependency factory**

In `backend/app/graphs/ingestion_nodes.py`, add:

```python
from app.graphs.ingestion_steps.dependencies import IngestionStepDependencies


def _ingestion_step_dependencies() -> IngestionStepDependencies:
    return IngestionStepDependencies(
        create_supabase_client=create_supabase_client,
        create_shopaikey_client=create_shopaikey_client,
        create_qdrant_client=create_qdrant_client,
        get_parser_for_file=get_parser_for_file,
        relations=relations,
    )
```

- [x] **Step 3: Move record state nodes**

Move these symbols to `backend/app/graphs/ingestion_steps/records.py`:

```text
load_document_record_node
mark_processing_node
```

Moved implementations must accept:

```python
def load_document_record_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    ...
```

Use `deps.create_supabase_client(settings=resolved_settings)` instead of direct factory references.

- [x] **Step 4: Add record wrappers in the facade**

In `backend/app/graphs/ingestion_nodes.py`, expose:

```python
def load_document_record_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _record_steps.load_document_record_node(
        state,
        settings=settings,
        deps=_ingestion_step_dependencies(),
    )


def mark_processing_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _record_steps.mark_processing_node(
        state,
        settings=settings,
        deps=_ingestion_step_dependencies(),
    )
```

- [x] **Step 5: Run ingestion tests after record move**

Run from `backend/`:

```powershell
python -m pytest tests/test_ingestion_graph.py -q
```

Expected:

```text
passed
```

- [x] **Step 6: Move parse and chunk nodes**

Move:

```text
parse_document_node -> backend/app/graphs/ingestion_steps/parsing.py
chunk_document_node -> backend/app/graphs/ingestion_steps/chunking.py
```

Use `deps.get_parser_for_file(...)` inside parsing.

- [x] **Step 7: Add parse and chunk wrappers**

In `backend/app/graphs/ingestion_nodes.py`, expose wrappers for:

```text
parse_document_node
chunk_document_node
```

Each wrapper must pass `_ingestion_step_dependencies()`.

- [x] **Step 8: Run parsing/chunking tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_ingestion_graph.py tests/test_chunker.py -q
```

Expected:

```text
passed
```

- [x] **Step 9: Move chunk persistence and summary nodes**

Move:

```text
save_chunks_node -> backend/app/graphs/ingestion_steps/persistence.py
summarize_document_node -> backend/app/graphs/ingestion_steps/summaries.py
```

Use `deps.create_supabase_client(settings=resolved_settings)` and `deps.create_shopaikey_client(settings=resolved_settings)`.

- [x] **Step 10: Add persistence and summary wrappers**

In `backend/app/graphs/ingestion_nodes.py`, expose wrappers for:

```text
save_chunks_node
summarize_document_node
```

- [x] **Step 11: Move vector indexing nodes**

Move:

```text
embed_chunks_node
upsert_qdrant_node
```

to `backend/app/graphs/ingestion_steps/indexing.py`.

Use:

```python
embedding_client = deps.create_shopaikey_client(settings=resolved_settings)
qdrant_client = deps.create_qdrant_client(settings=resolved_settings)
```

- [x] **Step 12: Add indexing wrappers**

In `backend/app/graphs/ingestion_nodes.py`, expose wrappers for:

```text
embed_chunks_node
upsert_qdrant_node
```

- [x] **Step 13: Move relation and finalization nodes**

Move:

```text
update_document_relations_node -> backend/app/graphs/ingestion_steps/relations.py
mark_ready_node -> backend/app/graphs/ingestion_steps/finalization.py
mark_failed_node -> backend/app/graphs/ingestion_steps/finalization.py
```

Use `deps.relations.update_document_relations(...)` in relation step code.

- [x] **Step 14: Add relation and finalization wrappers**

In `backend/app/graphs/ingestion_nodes.py`, expose wrappers for:

```text
update_document_relations_node
mark_ready_node
mark_failed_node
```

- [x] **Step 15: Preserve facade exports**

At the bottom of `backend/app/graphs/ingestion_nodes.py`, keep all existing `__all__` names. If `__all__` does not exist, add one containing every public node and compatibility alias currently imported by tests.

- [x] **Step 16: Run ingestion/API tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_ingestion_graph.py tests/test_ingestion_inputs.py tests/test_ingestion_payloads.py tests/test_api_documents.py -q
```

Expected:

```text
passed
```

- [x] **Step 17: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 18: Commit task**

Run from repository root:

```powershell
git add backend/app/graphs/ingestion_nodes.py backend/app/graphs/ingestion_steps backend/tests/test_ingestion_graph.py
git commit -m "refactor: split ingestion graph node steps"
```

---

## Task 6: Split retrieval service internals behind the existing facade

**Files:**
- Create: `backend/app/services/retrieval_normalization.py`
- Create: `backend/app/services/retrieval_filters.py`
- Create: `backend/app/services/semantic_retrieval.py`
- Create: `backend/app/services/reranking.py`
- Modify: `backend/app/services/retrieval.py`
- Test: `backend/tests/test_query_graph.py`
- Test: `backend/tests/test_score_fusion.py`
- Test: `backend/tests/test_retrieval_hints.py`

- [x] **Step 1: Move normalization helpers**

Move retrieval-only normalization helpers from `backend/app/services/retrieval.py` to `backend/app/services/retrieval_normalization.py`.

Keep these names available from `retrieval.py` by importing them back:

```python
from app.services.retrieval_normalization import (
    _normalize_float,
    _normalize_int,
    _normalize_text,
    _normalize_uuid,
    _response_rows,
)
```

Use the exact helper names present in the current file.

- [x] **Step 2: Run retrieval tests after normalization move**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_score_fusion.py -q
```

Expected:

```text
passed
```

- [x] **Step 3: Move Qdrant filter construction**

Move filter-building helpers from `backend/app/services/retrieval.py` to `backend/app/services/retrieval_filters.py`.

Keep the existing public entry point imported by `retrieval.py`:

```python
from app.services.retrieval_filters import build_qdrant_filter
```

If the current public helper is named differently, keep that exact name exported from `retrieval.py`.

- [x] **Step 4: Run filter-related tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_contracts.py -q
```

Expected:

```text
passed
```

- [x] **Step 5: Move semantic retrieval implementation**

Move these implementations to `backend/app/services/semantic_retrieval.py`:

```text
embed_question
search_semantic_chunks
retrieve_semantic_candidates
```

In `semantic_retrieval.py`, keep dependencies injectable:

```python
def embed_question(
    question: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> list[float]:
    ...
```

Keep `retrieval.py` facade functions with the same public names:

```python
def embed_question(*args: Any, **kwargs: Any) -> list[float]:
    return semantic_retrieval.embed_question(*args, **kwargs)
```

- [x] **Step 6: Preserve monkeypatch compatibility in hybrid retrieval**

In `backend/app/services/retrieval.py`, any function that calls semantic helpers must call the facade-level names, not the moved module directly.

Required pattern:

```python
embedding = embed_question(question, settings=resolved_settings, client=client)
semantic_candidates = search_semantic_chunks(
    embedding,
    filters=filters,
    settings=resolved_settings,
    client=qdrant_client,
)
```

This keeps tests that patch `retrieval.embed_question` or `retrieval.search_semantic_chunks` valid.

- [x] **Step 7: Run semantic retrieval compatibility tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_score_fusion.py tests/test_query_graph.py -q
```

Expected:

```text
passed
```

- [x] **Step 8: Move reranking implementation**

Move `rerank_chunks` implementation to `backend/app/services/reranking.py`.

Keep `retrieval.py` facade:

```python
def rerank_chunks(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return reranking.rerank_chunks(*args, **kwargs)
```

- [x] **Step 9: Run rerank tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_query_graph.py tests/test_retrieval_hints.py -q
```

Expected:

```text
passed
```

- [x] **Step 10: Keep hybrid orchestration in the facade for now**

Keep `retrieve_hybrid_chunks` and legacy `retrieve_context_chunks` orchestration inside `backend/app/services/retrieval.py` until all callers are less coupled. This protects tests that monkeypatch facade-level functions.

- [x] **Step 11: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 12: Commit task**

Run from repository root:

```powershell
git add backend/app/services/retrieval.py backend/app/services/retrieval_normalization.py backend/app/services/retrieval_filters.py backend/app/services/semantic_retrieval.py backend/app/services/reranking.py backend/tests/test_score_fusion.py
git commit -m "refactor: split retrieval service internals"
```

---

## Task 7: Final cleanup and regression verification

**Files:**
- Modify: `backend/README.md`
- Modify: `README.md`
- Inspect: all files changed by Tasks 1-6

- [x] **Step 1: Search for duplicate active env blocks**

Run from repository root:

```powershell
rg -n "^(APP_ENV|FRONTEND_ORIGIN|ADMIN_API_TOKEN|SUPABASE_URL|SHOPAIKEY_API_KEY|QDRANT_URL|JINA_API_KEY)=" README.md backend/README.md backend/app backend/tests
```

Expected:

```text
backend/tests/test_config.py
```

The active docs must not contain backend env assignment lines. The test file may contain env names because it verifies the contract.

- [x] **Step 2: Search for graph-layer imports from services**

Run from repository root:

```powershell
rg -n "from app\\.graphs\\.query_(prompts|formatting)|import app\\.graphs\\.query_(prompts|formatting)" backend/app/services
```

Expected:

```text
no matches
```

- [x] **Step 3: Confirm compatibility modules still import**

Run from `backend/`:

```powershell
python - <<'PY'
from app.graphs import query_nodes, ingestion_nodes
from app.services import retrieval
from app.graphs import query_prompts, query_formatting

for module, names in {
    query_nodes: ["prepare_query_node", "generate_answer_node", "save_message_optional_node"],
    ingestion_nodes: ["load_document_record_node", "upsert_qdrant_node", "mark_failed_node"],
    retrieval: ["embed_question", "search_semantic_chunks", "rerank_chunks"],
    query_prompts: ["build_answer_messages", "build_query_planning_messages"],
    query_formatting: ["build_context_prompt", "build_source_citations"],
}.items():
    for name in names:
        assert callable(getattr(module, name)), (module.__name__, name)
print("compat imports ok")
PY
```

Expected:

```text
compat imports ok
```

- [x] **Step 4: Run targeted suites**

Run from `backend/`:

```powershell
python -m pytest tests/test_config.py tests/test_query_graph.py tests/test_ingestion_graph.py tests/test_score_fusion.py tests/test_api_documents.py tests/test_api_chat.py -q
```

Expected:

```text
passed
```

- [x] **Step 5: Run full backend tests**

Run from `backend/`:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 6: Inspect diff for accidental behavior changes**

Run from repository root:

```powershell
git diff --stat
git diff -- backend/app/api backend/app/models backend/app/core/contracts.py
```

Expected:

```text
No API route behavior, schema names, or core contract constants changed.
```

- [x] **Step 7: Commit final cleanup**

Run from repository root:

```powershell
git add README.md backend/README.md backend/app backend/tests backend/.env.example
git commit -m "refactor: complete backend compatibility cleanup"
```/.env.example
git commit -m "refactor: complete backend compatibility cleanup"
```

---

## Completion criteria

- `python -m pytest -q` passes from `backend/`.
- `backend/.env.example` exists and lists every `Settings` field exactly once.
- Active README files point to `backend/.env.example` instead of duplicating env assignments.
- `backend/.env` remains untracked and untouched.
- Public compatibility imports still work.
- Existing monkeypatch-heavy tests still pass.
- No endpoint, schema, graph edge, retrieval fallback, citation, grounding, trace redaction, or message persistence behavior changes are introduced by the refactor.

## Self-review notes

- Spec coverage: backend refactor, compatibility facades, env centralization, tests, and docs are covered.
- Placeholder scan: no incomplete plan sections remain; env example values are intentional sample values for user setup.
- Type consistency: dependency object names, module names, and wrapper signatures are consistent across query and ingestion tasks.
