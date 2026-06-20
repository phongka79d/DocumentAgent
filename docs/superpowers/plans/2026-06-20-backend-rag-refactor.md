# Backend RAG Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `retrieval.py`, `ingestion_nodes.py`, and `query_nodes.py` so hardcoded prompts, schema keys, statuses, table names, and retrieval boundary rules are centralized and the large files are split into focused modules.

**Architecture:** Keep public APIs stable while moving internals into smaller modules. LLM remains responsible for understanding user intent such as "beginning" and "end"; deterministic code resolves those hints into chunk indexes and database reads.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, LangGraph, Supabase client, Qdrant client, OpenAI-compatible ShopAIKey client, pytest.

---

## File Structure

- Create `backend/app/core/contracts.py`: shared table names, status strings, chunking strategy/version strings, payload keys, context modes, retrieval boundary names, and preview length.
- Modify `backend/app/core/config.py`: add retrieval-hint and boundary settings.
- Create `backend/app/graphs/query_prompts.py`: answer prompt, no-result message, and answer-message builder.
- Create `backend/app/graphs/query_formatting.py`: context formatting, source citation formatting, chat-content extraction, and message metadata helpers.
- Modify `backend/app/graphs/query_nodes.py`: keep node functions only; import prompts/formatters and use message service for persistence.
- Modify `backend/app/services/messages.py`: add `create_message` so graph code does not hardcode the `"messages"` table.
- Create `backend/app/services/retrieval_hints.py`: LLM prompt, JSON parsing, and hint extraction.
- Create `backend/app/services/retrieval_boundaries.py`: deterministic conversion from LLM boundary hints to beginning/end chunks.
- Create `backend/app/services/retrieval_context.py`: context chunk normalization and neighbor/section-aware context expansion.
- Modify `backend/app/services/retrieval.py`: keep high-level retrieval orchestration and semantic/rerank calls; delegate hint/context work.
- Create `backend/app/graphs/ingestion_payloads.py`: ingestion payload builders, status helpers, and chunker strategy resolution.
- Modify `backend/app/graphs/ingestion_nodes.py`: keep node functions only; import payload/status helpers.
- Modify tests in `backend/tests/test_config.py`, `backend/tests/test_query_graph.py`, and `backend/tests/test_ingestion_graph.py`.
- Add tests `backend/tests/test_contracts.py`, `backend/tests/test_retrieval_hints.py`, and `backend/tests/test_retrieval_boundaries.py`.

---

### Task 1: Add Contract And Settings Tests

**Files:**
- Modify: `backend/tests/test_config.py`
- Create: `backend/tests/test_contracts.py`

- [x] **Step 1: Write failing settings assertions**

In `backend/tests/test_config.py`, add these names to `ALL_SETTINGS_FIELDS`:

```python
    "RETRIEVAL_HINT_TEMPERATURE",
    "RETRIEVAL_HINT_MAX_TOKENS",
    "RETRIEVAL_BOUNDARY_START_CHUNKS",
    "RETRIEVAL_BOUNDARY_END_CHUNKS",
```

In `test_settings_load_defaults_from_master_plan`, add:

```python
    assert settings.RETRIEVAL_HINT_TEMPERATURE == 0.0
    assert settings.RETRIEVAL_HINT_MAX_TOKENS == 120
    assert settings.RETRIEVAL_BOUNDARY_START_CHUNKS == 2
    assert settings.RETRIEVAL_BOUNDARY_END_CHUNKS == 2
```

In `test_settings_read_environment_overrides`, add:

```python
    monkeypatch.setenv("RETRIEVAL_HINT_TEMPERATURE", "0.1")
    monkeypatch.setenv("RETRIEVAL_HINT_MAX_TOKENS", "160")
    monkeypatch.setenv("RETRIEVAL_BOUNDARY_START_CHUNKS", "3")
    monkeypatch.setenv("RETRIEVAL_BOUNDARY_END_CHUNKS", "4")
```

Then assert:

```python
    assert settings.RETRIEVAL_HINT_TEMPERATURE == 0.1
    assert settings.RETRIEVAL_HINT_MAX_TOKENS == 160
    assert settings.RETRIEVAL_BOUNDARY_START_CHUNKS == 3
    assert settings.RETRIEVAL_BOUNDARY_END_CHUNKS == 4
```

- [x] **Step 2: Write failing contract tests**

Create `backend/tests/test_contracts.py`:

```python
from app.core.contracts import (
    ChunkingStrategy,
    ChunkingVersion,
    ContextMode,
    DocumentStatus,
    QdrantPayloadKey,
    RetrievalBoundary,
    SOURCE_PREVIEW_CHARS,
    TableName,
)


def test_shared_contract_literals_match_database_and_api_values():
    assert TableName.DOCUMENTS == "documents"
    assert TableName.DOCUMENT_CHUNKS == "document_chunks"
    assert TableName.MESSAGES == "messages"

    assert DocumentStatus.FAILED == "failed"
    assert DocumentStatus.PROCESSING == "processing"
    assert DocumentStatus.READY == "ready"

    assert ChunkingStrategy.FIXED_TOKEN == "fixed_token"
    assert ChunkingStrategy.SMART_SECTION == "smart_section"
    assert ChunkingVersion.FIXED_TOKEN == "v1"
    assert ChunkingVersion.SMART_SECTION == "v2"

    assert ContextMode.NEIGHBOR == "neighbor"
    assert ContextMode.SECTION_AWARE == "section_aware"
    assert RetrievalBoundary.BEGINNING == "beginning"
    assert RetrievalBoundary.END == "end"

    assert QdrantPayloadKey.DOCUMENT_ID == "document_id"
    assert QdrantPayloadKey.CHUNK_ID == "chunk_id"
    assert QdrantPayloadKey.TEXT == "text"
    assert SOURCE_PREVIEW_CHARS == 240
```

- [x] **Step 3: Run tests and verify failure**

Run:

```bash
cd backend
pytest tests/test_config.py tests/test_contracts.py -v
```

Expected: `test_contracts.py` fails because `app.core.contracts` does not exist, and `test_config.py` fails because new settings fields do not exist.

- [x] **Step 4: Commit tests**

```bash
git add backend/tests/test_config.py backend/tests/test_contracts.py
git commit -m "test: add backend refactor contract coverage"
```

---

### Task 2: Add Shared Contracts And New Settings

**Files:**
- Create: `backend/app/core/contracts.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_config.py`, `backend/tests/test_contracts.py`

- [x] **Step 1: Create shared contracts**

Create `backend/app/core/contracts.py`:

```python
from enum import StrEnum


class TableName(StrEnum):
    DOCUMENTS = "documents"
    DOCUMENT_CHUNKS = "document_chunks"
    MESSAGES = "messages"


class DocumentStatus(StrEnum):
    FAILED = "failed"
    PROCESSING = "processing"
    READY = "ready"


class ChunkingStrategy(StrEnum):
    FIXED_TOKEN = "fixed_token"
    SMART_SECTION = "smart_section"


class ChunkingVersion(StrEnum):
    FIXED_TOKEN = "v1"
    SMART_SECTION = "v2"


class ContextMode(StrEnum):
    NEIGHBOR = "neighbor"
    SECTION_AWARE = "section_aware"


class RetrievalBoundary(StrEnum):
    BEGINNING = "beginning"
    END = "end"


class ChunkField(StrEnum):
    DOCUMENT_ID = "document_id"
    CHUNK_INDEX = "chunk_index"
    CONTENT = "content"
    CONTENT_HASH = "content_hash"
    TOKEN_COUNT = "token_count"
    CHUNK_TYPE = "chunk_type"
    HEADING = "heading"
    SECTION_PATH = "section_path"
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    TOKEN_START = "token_start"
    TOKEN_END = "token_end"
    METADATA = "metadata"


class QdrantPayloadKey(StrEnum):
    ID = "id"
    CHUNK_ID = "chunk_id"
    DOCUMENT_ID = "document_id"
    FILE_NAME = "file_name"
    CHUNK_INDEX = "chunk_index"
    CONTENT = "content"
    TEXT = "text"
    HEADING = "heading"
    SECTION_PATH = "section_path"
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    CHUNK_TYPE = "chunk_type"
    TOKEN_COUNT = "token_count"


class MessageField(StrEnum):
    QUESTION = "question"
    ANSWER = "answer"
    SOURCES = "sources"
    METADATA = "metadata"


SOURCE_PREVIEW_CHARS = 240
```

- [x] **Step 2: Add settings**

In `backend/app/core/config.py`, add after `RETRIEVAL_CONTEXT_MAX_CANDIDATES`:

```python
    RETRIEVAL_HINT_TEMPERATURE: float = 0.0
    RETRIEVAL_HINT_MAX_TOKENS: int = 120
    RETRIEVAL_BOUNDARY_START_CHUNKS: int = 2
    RETRIEVAL_BOUNDARY_END_CHUNKS: int = 2
```

- [x] **Step 3: Run tests**

Run:

```bash
cd backend
pytest tests/test_config.py tests/test_contracts.py -v
```

Expected: all selected tests pass.

- [x] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/app/core/contracts.py backend/tests/test_config.py backend/tests/test_contracts.py
git commit -m "refactor: centralize backend contracts"
```

---

### Task 3: Extract Query Prompts And Formatting

**Files:**
- Create: `backend/app/graphs/query_prompts.py`
- Create: `backend/app/graphs/query_formatting.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Test: `backend/tests/test_query_graph.py`

- [x] **Step 1: Write a regression test for configurable preview length**

Add to `backend/tests/test_query_graph.py`:

```python
def test_source_citation_preview_uses_shared_limit():
    long_content = "x" * 300
    citation = query_nodes._build_source_citations(
        [
            {
                "document_id": DOC_A,
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "content": long_content,
            }
        ]
    )[0]

    assert citation["content_preview"] == "x" * 240
```

- [x] **Step 2: Run test before refactor**

Run:

```bash
cd backend
pytest tests/test_query_graph.py::test_source_citation_preview_uses_shared_limit -v
```

Expected: pass before refactor, proving behavior is captured.

- [x] **Step 3: Create query prompt module**

Create `backend/app/graphs/query_prompts.py`:

```python
from collections.abc import Mapping


ANSWER_SYSTEM_PROMPT = (
    "You are a personal document RAG assistant.\n\n"
    "Rules:\n"
    "- Answer using only the provided context.\n"
    "- If the context does not contain enough information, say that the indexed documents do not contain enough information.\n"
    "- Do not invent facts.\n"
    "- Do not invent sources.\n"
    "- Cite the source chunks used in the answer.\n"
    "- Keep the answer clear and practical."
)

ANSWER_USER_PROMPT_TEMPLATE = (
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer using only the context."
)

NO_RELEVANT_INFORMATION_MESSAGE = "No relevant information found in indexed documents."


def build_answer_messages(*, context: str, question: str) -> list[Mapping[str, str]]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ANSWER_USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            ),
        },
    ]
```

- [x] **Step 4: Create query formatting module**

Create `backend/app/graphs/query_formatting.py` by moving these functions from `query_nodes.py` without changing behavior:

```python
_normalize_text
_normalize_int
_normalize_float
_normalize_section_path
_chunk_content_preview
_resolve_context_chunks
_chunk_content
_format_page_range
_format_context_chunk
_build_context_prompt
_source_citation_from_chunk
_build_source_citations
_message_metadata
_extract_chat_content
```

Change `_chunk_content_preview` to use:

```python
from app.core.contracts import SOURCE_PREVIEW_CHARS


def _chunk_content_preview(chunk: Mapping[str, Any]) -> str:
    content = chunk.get("content")
    if content is None:
        content = chunk.get("text")
    if content is None:
        return ""
    return str(content)[:SOURCE_PREVIEW_CHARS]
```

- [x] **Step 5: Update query nodes imports**

In `backend/app/graphs/query_nodes.py`, remove moved helper bodies and import:

```python
from app.graphs.query_formatting import (
    _build_context_prompt,
    _build_source_citations,
    _extract_chat_content,
    _message_metadata,
    _normalize_document_ids,
    _normalize_text,
    _resolve_context_chunks,
)
from app.graphs.query_prompts import (
    NO_RELEVANT_INFORMATION_MESSAGE,
    build_answer_messages,
)
```

Keep `_normalize_document_ids` in `query_nodes.py` if it is only used by node input handling.

In `generate_answer_node`, replace manual prompt construction with:

```python
        response = client.chat.completions.create(
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            messages=build_answer_messages(context=context, question=question),
            temperature=resolved_settings.TEMPERATURE,
            max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
        )
```

- [x] **Step 6: Preserve backward-compatible test access**

At the bottom of `query_nodes.py`, keep these aliases so current tests do not break:

```python
_build_context_prompt = _build_context_prompt
_build_source_citations = _build_source_citations
_extract_chat_content = _extract_chat_content
```

- [x] **Step 7: Run query tests**

Run:

```bash
cd backend
pytest tests/test_query_graph.py -v
```

Expected: all query graph tests pass.

- [x] **Step 8: Commit**

```bash
git add backend/app/graphs/query_nodes.py backend/app/graphs/query_prompts.py backend/app/graphs/query_formatting.py backend/tests/test_query_graph.py
git commit -m "refactor: split query prompts and formatting"
```

---

### Task 4: Remove Direct Message Table Write From Query Node

**Files:**
- Modify: `backend/app/services/messages.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Test: `backend/tests/test_query_graph.py`

- [x] **Step 1: Add message service write helper**

In `backend/app/services/messages.py`, import:

```python
from app.core.contracts import MessageField, TableName
```

Replace:

```python
MESSAGES_TABLE = "messages"
```

with:

```python
MESSAGES_TABLE = TableName.MESSAGES
```

Add:

```python
def create_message(
    *,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    metadata: dict[str, Any],
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> None:
    _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    payload = {
        MessageField.QUESTION: question,
        MessageField.ANSWER: answer,
        MessageField.SOURCES: sources,
        MessageField.METADATA: metadata,
    }
    client.table(MESSAGES_TABLE).insert(payload).execute()
```

- [x] **Step 2: Update query node**

In `backend/app/graphs/query_nodes.py`, replace:

```python
from app.services.supabase_client import create_supabase_client
```

with:

```python
from app.services import messages as message_service
```

In `save_message_optional_node`, replace direct `client.table("messages").insert(payload).execute()` with:

```python
        message_service.create_message(
            question=question,
            answer=answer,
            sources=normalized_sources,
            metadata=_message_metadata(state),
            settings=resolved_settings,
            supabase_client=supabase_client,
        )
```

- [x] **Step 3: Run query tests**

Run:

```bash
cd backend
pytest tests/test_query_graph.py tests/test_api_messages.py -v
```

Expected: all selected tests pass.

- [x] **Step 4: Commit**

```bash
git add backend/app/services/messages.py backend/app/graphs/query_nodes.py
git commit -m "refactor: persist chat messages through service"
```

---

### Task 5: Extract LLM Retrieval Hints

**Files:**
- Create: `backend/app/services/retrieval_hints.py`
- Modify: `backend/app/services/retrieval.py`
- Create: `backend/tests/test_retrieval_hints.py`

- [x] **Step 1: Write tests for LLM hint settings and parsing**

Create `backend/tests/test_retrieval_hints.py`:

```python
from types import SimpleNamespace

from app.core.config import Settings
from app.services import retrieval_hints


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeShopAIKeyClient:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def test_extract_retrieval_hints_uses_settings_for_llm_call():
    settings = Settings(
        _env_file=None,
        SHOPAIKEY_CHAT_MODEL="gpt-5-mini",
        RETRIEVAL_HINT_TEMPERATURE=0.1,
        RETRIEVAL_HINT_MAX_TOKENS=160,
    )
    client = FakeShopAIKeyClient('{"boundary_positions":["beginning","end"]}')

    result = retrieval_hints.extract_retrieval_hints(
        "compare intro and conclusion",
        settings=settings,
        shopaikey_client=client,
    )

    assert result == {"boundary_positions": ["beginning", "end"]}
    assert client.completions.calls[0]["temperature"] == 0.1
    assert client.completions.calls[0]["max_tokens"] == 160


def test_extract_retrieval_hints_ignores_unknown_boundaries():
    settings = Settings(_env_file=None)
    client = FakeShopAIKeyClient('{"boundary_positions":["beginning","middle","end"]}')

    result = retrieval_hints.extract_retrieval_hints(
        "read the beginning and end",
        settings=settings,
        shopaikey_client=client,
    )

    assert result == {"boundary_positions": ["beginning", "end"]}
```

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
pytest tests/test_retrieval_hints.py -v
```

Expected: fails because `app.services.retrieval_hints` does not exist.

- [x] **Step 3: Create retrieval hint module**

Create `backend/app/services/retrieval_hints.py` by moving from `retrieval.py`:

```python
RETRIEVAL_HINT_SYSTEM_PROMPT
RETRIEVAL_HINT_USER_PROMPT_TEMPLATE
_extract_chat_content
_normalize_retrieval_hints
extract_retrieval_hints
```

Use contract constants:

```python
from app.core.contracts import RetrievalBoundary
```

In the LLM call, use settings:

```python
            temperature=resolved_settings.RETRIEVAL_HINT_TEMPERATURE,
            max_tokens=resolved_settings.RETRIEVAL_HINT_MAX_TOKENS,
```

Normalize boundaries with:

```python
ALLOWED_BOUNDARIES = {boundary.value for boundary in RetrievalBoundary}
```

- [x] **Step 4: Update retrieval service**

In `backend/app/services/retrieval.py`, remove moved prompt/hint functions and import:

```python
from app.services.retrieval_hints import extract_retrieval_hints
```

Keep `extract_retrieval_hints` available from `retrieval.py` for compatibility:

```python
extract_retrieval_hints = extract_retrieval_hints
```

- [x] **Step 5: Run retrieval tests**

Run:

```bash
cd backend
pytest tests/test_retrieval_hints.py tests/test_query_graph.py -v
```

Expected: all selected tests pass.

- [x] **Step 6: Commit**

```bash
git add backend/app/services/retrieval.py backend/app/services/retrieval_hints.py backend/tests/test_retrieval_hints.py
git commit -m "refactor: extract llm retrieval hints"
```

---

### Task 6: Add Deterministic Boundary Chunk Resolver

**Files:**
- Create: `backend/app/services/retrieval_boundaries.py`
- Modify: `backend/app/services/retrieval.py`
- Create: `backend/tests/test_retrieval_boundaries.py`

- [ ] **Step 1: Write boundary resolver tests**

Create `backend/tests/test_retrieval_boundaries.py`:

```python
from dataclasses import dataclass, field

from app.core.config import Settings
from app.services import retrieval_boundaries


@dataclass
class FakeChunkStore:
    by_index_calls: list[tuple[str, list[int]]] = field(default_factory=list)
    last_calls: list[str] = field(default_factory=list)

    def get_chunks_by_document_and_indexes(self, document_id, indexes, **kwargs):
        resolved_indexes = list(indexes)
        self.by_index_calls.append((str(document_id), resolved_indexes))
        return [
            {
                "id": f"chunk-{index}",
                "document_id": str(document_id),
                "chunk_index": index,
                "content": f"chunk {index}",
            }
            for index in resolved_indexes
        ]

    def get_last_chunk_by_document(self, document_id, **kwargs):
        self.last_calls.append(str(document_id))
        return {
            "id": "chunk-9",
            "document_id": str(document_id),
            "chunk_index": 9,
            "content": "chunk 9",
        }


def test_get_boundary_chunks_reads_configured_beginning_and_end_windows(monkeypatch):
    store = FakeChunkStore()
    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_chunks_by_document_and_indexes",
        store.get_chunks_by_document_and_indexes,
    )
    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_last_chunk_by_document",
        store.get_last_chunk_by_document,
    )
    settings = Settings(
        _env_file=None,
        RETRIEVAL_BOUNDARY_START_CHUNKS=2,
        RETRIEVAL_BOUNDARY_END_CHUNKS=3,
    )

    chunks = retrieval_boundaries.get_boundary_chunks(
        "doc-1",
        ["beginning", "end"],
        settings=settings,
        supabase_client=object(),
    )

    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 7, 8, 9]
    assert store.by_index_calls == [("doc-1", [0, 1]), ("doc-1", [7, 8, 9])]
    assert store.last_calls == ["doc-1"]
```

- [ ] **Step 2: Run boundary tests and verify failure**

Run:

```bash
cd backend
pytest tests/test_retrieval_boundaries.py -v
```

Expected: fails because `app.services.retrieval_boundaries` does not exist.

- [ ] **Step 3: Create boundary resolver**

Create `backend/app/services/retrieval_boundaries.py`:

```python
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.contracts import RetrievalBoundary
from app.services import chunks as chunk_service


def _positive_window(value: int) -> int:
    return max(0, int(value))


def _unique_positions(boundary_positions: Sequence[str]) -> list[str]:
    allowed = {boundary.value for boundary in RetrievalBoundary}
    selected: list[str] = []
    seen: set[str] = set()
    for raw_position in boundary_positions:
        position = str(raw_position).strip().lower()
        if position in allowed and position not in seen:
            selected.append(position)
            seen.add(position)
    return selected


def get_boundary_chunks(
    document_id: UUID | str,
    boundary_positions: Sequence[str],
    *,
    settings: Settings,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    selected_positions = _unique_positions(boundary_positions)
    chunks: list[dict[str, Any]] = []

    if RetrievalBoundary.BEGINNING in selected_positions:
        start_window = _positive_window(settings.RETRIEVAL_BOUNDARY_START_CHUNKS)
        if start_window:
            chunks.extend(
                chunk_service.get_chunks_by_document_and_indexes(
                    document_id,
                    range(start_window),
                    settings=settings,
                    supabase_client=supabase_client,
                )
            )

    if RetrievalBoundary.END in selected_positions:
        end_window = _positive_window(settings.RETRIEVAL_BOUNDARY_END_CHUNKS)
        last_chunk = chunk_service.get_last_chunk_by_document(
            document_id,
            settings=settings,
            supabase_client=supabase_client,
        )
        if end_window and last_chunk is not None:
            last_index = int(last_chunk["chunk_index"])
            first_index = max(0, last_index - end_window + 1)
            chunks.extend(
                chunk_service.get_chunks_by_document_and_indexes(
                    document_id,
                    range(first_index, last_index + 1),
                    settings=settings,
                    supabase_client=supabase_client,
                )
            )

    return chunks
```

- [ ] **Step 4: Wire into retrieval context path**

In `backend/app/services/retrieval.py`, replace direct beginning/end logic with:

```python
from app.services.retrieval_boundaries import get_boundary_chunks
```

Inside boundary expansion, call:

```python
boundary_rows = get_boundary_chunks(
    document_id,
    boundary_positions,
    settings=settings,
    supabase_client=supabase_client,
)
```

Normalize each returned row with the existing context chunk normalizer.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_retrieval_boundaries.py tests/test_query_graph.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/retrieval.py backend/app/services/retrieval_boundaries.py backend/tests/test_retrieval_boundaries.py
git commit -m "refactor: resolve retrieval boundaries deterministically"
```

---

### Task 7: Split Retrieval Context Expansion

**Files:**
- Create: `backend/app/services/retrieval_context.py`
- Modify: `backend/app/services/retrieval.py`
- Test: `backend/tests/test_query_graph.py`

- [ ] **Step 1: Add public behavior regression test**

In `backend/tests/test_query_graph.py`, add a test that calls `retrieval.expand_neighbor_context` in `section_aware` mode and asserts returned chunks still include semantic chunks first, section siblings next, and generic neighbors last.

Use existing fake Supabase/chunk fixtures in the file. The expected order should be exact:

```python
assert [chunk["chunk_id"] for chunk in context_chunks] == [
    "semantic-anchor",
    "section-prev",
    "section-next",
    "generic-prev",
    "generic-next",
]
```

- [ ] **Step 2: Run regression test**

Run:

```bash
cd backend
pytest tests/test_query_graph.py -k "section_aware" -v
```

Expected: pass before moving code.

- [ ] **Step 3: Create retrieval context module**

Create `backend/app/services/retrieval_context.py` by moving these functions from `retrieval.py`:

```python
_normalize_context_mode
_normalize_section_path
_normalize_context_chunk
_neighbor_indexes
_append_normalized_context_chunks
_expand_neighbor_context_legacy
_expand_neighbor_context_section_aware
expand_neighbor_context
```

Use constants:

```python
from app.core.contracts import ContextMode, QdrantPayloadKey
```

Replace context mode comparisons with:

```python
if context_mode == ContextMode.NEIGHBOR:
    ...
if context_mode == ContextMode.SECTION_AWARE:
    ...
```

Replace hardcoded payload reads where useful:

```python
chunk.get(QdrantPayloadKey.CHUNK_ID) or chunk.get(QdrantPayloadKey.ID)
chunk.get(QdrantPayloadKey.DOCUMENT_ID)
chunk.get(QdrantPayloadKey.CONTENT) or chunk.get(QdrantPayloadKey.TEXT)
```

- [ ] **Step 4: Update retrieval service imports**

In `backend/app/services/retrieval.py`, import:

```python
from app.services.retrieval_context import (
    expand_neighbor_context,
    normalize_context_chunk,
)
```

Keep `expand_neighbor_context` re-exported from `retrieval.py` because `query_nodes.py` already imports it from `app.services.retrieval`.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_query_graph.py tests/test_retrieval_boundaries.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/retrieval.py backend/app/services/retrieval_context.py backend/tests/test_query_graph.py
git commit -m "refactor: split retrieval context expansion"
```

---

### Task 8: Extract Ingestion Payloads And Status Contracts

**Files:**
- Create: `backend/app/graphs/ingestion_payloads.py`
- Modify: `backend/app/graphs/ingestion_nodes.py`
- Test: `backend/tests/test_ingestion_graph.py`

- [ ] **Step 1: Write stale default regression test**

Add to `backend/tests/test_ingestion_graph.py`:

```python
def test_resolve_chunker_rejects_unknown_strategy_without_fixed_token_fallback():
    settings = _test_settings(chunking_strategy="unknown")

    with pytest.raises(ValueError, match="Unsupported chunking strategy: unknown"):
        ingestion_nodes._resolve_chunker_for_settings(settings)
```

- [ ] **Step 2: Run regression test**

Run:

```bash
cd backend
pytest tests/test_ingestion_graph.py::test_resolve_chunker_rejects_unknown_strategy_without_fixed_token_fallback -v
```

Expected: pass before refactor, documenting that no fallback should occur.

- [ ] **Step 3: Create ingestion payload module**

Create `backend/app/graphs/ingestion_payloads.py` by moving these functions from `ingestion_nodes.py`:

```python
_failure_state
_chunk_metadata
_document_chunk_insert_payload
_qdrant_payload
_build_qdrant_point
_resolve_chunker_for_settings
```

Use contracts:

```python
from app.core.contracts import (
    ChunkField,
    ChunkingStrategy,
    ChunkingVersion,
    DocumentStatus,
    QdrantPayloadKey,
)
```

Replace hardcoded status and strategy/version values with contract constants. Do not define `DEFAULT_CHUNKING_STRATEGY`; unsupported settings must raise `ValueError`.

- [ ] **Step 4: Update ingestion nodes**

In `backend/app/graphs/ingestion_nodes.py`, remove moved helpers and import:

```python
from app.graphs.ingestion_payloads import (
    _build_qdrant_point,
    _chunk_metadata,
    _document_chunk_insert_payload,
    _failure_state,
    _qdrant_payload,
    _resolve_chunker_for_settings,
)
from app.core.contracts import DocumentStatus, TableName
```

Replace:

```python
DOCUMENTS_TABLE = "documents"
DOCUMENT_CHUNKS_TABLE = "document_chunks"
```

with:

```python
DOCUMENTS_TABLE = TableName.DOCUMENTS
DOCUMENT_CHUNKS_TABLE = TableName.DOCUMENT_CHUNKS
```

Replace status literals in node return payloads with `DocumentStatus.PROCESSING`, `DocumentStatus.READY`, and `DocumentStatus.FAILED`.

- [ ] **Step 5: Preserve test compatibility**

At the bottom of `ingestion_nodes.py`, keep aliases for moved helpers used by tests:

```python
_failure_state = _failure_state
_resolve_chunker_for_settings = _resolve_chunker_for_settings
```

- [ ] **Step 6: Run ingestion tests**

Run:

```bash
cd backend
pytest tests/test_ingestion_graph.py -v
```

Expected: all ingestion graph tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/graphs/ingestion_nodes.py backend/app/graphs/ingestion_payloads.py backend/tests/test_ingestion_graph.py
git commit -m "refactor: split ingestion payload contracts"
```

---

### Task 9: Full Verification And Hardcode Audit

**Files:**
- Modify: only files changed by previous tasks if verification exposes failures.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd backend
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Verify file sizes decreased**

Run from repo root:

```bash
$files = @(
  "backend/app/services/retrieval.py",
  "backend/app/graphs/ingestion_nodes.py",
  "backend/app/graphs/query_nodes.py"
)
foreach ($f in $files) {
  [pscustomobject]@{ File = $f; Lines = @(Get-Content -LiteralPath $f).Count }
}
```

Expected: each listed file is smaller than before. Target sizes:

```text
backend/app/services/retrieval.py: below 500 lines
backend/app/graphs/ingestion_nodes.py: below 450 lines
backend/app/graphs/query_nodes.py: below 350 lines
```

- [ ] **Step 3: Re-run hardcode search**

Run:

```bash
rg -n '"messages"|DOCUMENTS_TABLE = "documents"|DOCUMENT_CHUNKS_TABLE = "document_chunks"|DEFAULT_CHUNKING_STRATEGY|temperature=0|max_tokens=80|\[:240\]|"neighbor"|"section_aware"|"beginning"|"end"' backend/app/services/retrieval.py backend/app/graphs/ingestion_nodes.py backend/app/graphs/query_nodes.py
```

Expected: no direct matches in the three original files except import names, user-facing error text, and references to contract constants.

- [ ] **Step 4: Run focused integration tests**

Run:

```bash
cd backend
pytest tests/test_query_graph.py tests/test_ingestion_graph.py tests/test_api_chat.py tests/test_api_documents.py tests/test_api_messages.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit verification fixes**

If any verification-only changes were needed:

```bash
git add backend/app backend/tests
git commit -m "test: verify backend rag refactor"
```

If no changes were needed, do not create an empty commit.

