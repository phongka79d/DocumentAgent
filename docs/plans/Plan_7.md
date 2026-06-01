# Plan 7 - Medium GraphRAG Data Model and Graph Builder

## 1. Goal

Build medium-level GraphRAG metadata by extracting entities from chunks, storing entities and relationships, and representing the graph path `Document -> Section -> Chunk -> Entity -> Relationship`.

The goal is testable when processed documents produce `document_entities` and `document_relationships` rows that can later support graph-based retrieval expansion.

## 2. Why This Plan Exists

Semantic search alone can miss related chunks that share entities, dates, policies, or conditions. This plan creates the structured graph layer needed for hybrid retrieval and Agent 1 scoring.

## 3. Scope

- Add entity extraction from chunk text.
- Add entity extraction prompt or deterministic fallback.
- Add Pydantic validation for extracted entities and relationships.
- Insert rows into `document_entities`.
- Insert rows into `document_relationships`.
- Create document-section, section-chunk, chunk-entity, entity-entity, and chunk-chunk relationship records where supported by available metadata.
- Add graph builder service.
- Add graph build tests.

## 4. Out of Scope

- Do not implement community detection.
- Do not implement graph visualization.
- Do not implement hybrid retrieval scoring.
- Do not implement Agent 1.
- Do not require perfect entity extraction.
- Do not use unvalidated LLM JSON directly.
- Do not expose graph APIs to frontend yet.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 2 must be completed.
- Plan 4 must be completed.
- Plan 5 may be completed but is not required for graph building.
- ShopAIKey chat completion config is required if LLM extraction is used.

## 6. Required Files and Folders

```text
backend/app/services/graph_builder.py
- Orchestrates entity extraction and relationship creation for a document.

backend/app/services/entity_extraction_service.py
- Extracts entities and relationships from chunk content using ShopAIKey or deterministic fallback.

backend/app/services/shopaikey_service.py
- Add chat completion helper for structured JSON extraction if not already present.

backend/app/services/supabase_service.py
- Add helpers for chunk lookup, entity inserts, relationship inserts, and clearing graph rows for rebuild.

backend/app/schemas/graph.py
- Contains EntityDraft, RelationshipDraft, GraphBuildResult, and validated LLM output models.

backend/tests/test_entity_extraction_service.py
- Tests valid JSON parsing, invalid JSON handling, and fallback behavior.

backend/tests/test_graph_builder.py
- Tests entity and relationship persistence with mocked Supabase.

backend/.env.example
- Add ShopAIKey chat model if not already present.
```

## 7. Data Model / Schema Changes

No database table changes in this plan.

Use existing `document_entities` and `document_relationships`.

Entity draft schema:

```json
{
  "entity_name": "Probation Period",
  "entity_type": "contract term",
  "description": "Duration before official employment consideration",
  "chunk_id": "uuid"
}
```

Relationship draft schema:

```json
{
  "source_type": "chunk",
  "source_id": "uuid",
  "target_type": "entity",
  "target_id": "uuid-or-entity-name-before-insert",
  "relationship_type": "chunk_mentions_entity",
  "weight": 0.8,
  "description": "Chunk mentions probation period"
}
```

Allowed entity types should include:

```text
person
date
organization
policy
contract term
job position
probation period
salary
deadline
condition
other
```

Allowed relationship types should include:

```text
document_contains_section
section_contains_chunk
chunk_mentions_entity
entity_related_to_entity
chunk_related_to_chunk
mentions
contains
requires
starts_at
ends_at
depends_on
related_to
```

## 8. API Design

No required public API endpoints in this plan.

Optional development-only endpoint if needed:

```text
Method: POST
Path: /api/documents/{document_id}/build-graph
Request body: none
Response body:
{
  "document_id": "uuid",
  "entity_count": 25,
  "relationship_count": 90
}
Error responses:
- 404 document not found for SINGLE_USER_ID
- 400 document has no chunks
- 500 entity extraction failure
- 500 database insert failure
```

## 9. Implementation Steps

1. Add `SHOPAIKEY_CHAT_MODEL` to settings and `.env.example` if not already present.
2. Add `chat_completion(messages, response_format=None)` to `shopaikey_service.py`.
3. Create graph schemas in `backend/app/schemas/graph.py`.
4. Implement `extract_entities_for_chunk(chunk)` in `entity_extraction_service.py`.
5. Prompt the model to return strict JSON containing entities and relationships only.
6. Validate LLM output with Pydantic before inserting anything.
7. If LLM JSON is invalid, return a controlled extraction error or fallback result; do not insert malformed rows.
8. Add a deterministic fallback that extracts obvious dates and repeated capitalized terms if LLM extraction is disabled in tests.
9. Implement `build_document_graph(document_id)` in `graph_builder.py`.
10. Fetch document and chunks filtered by `SINGLE_USER_ID`.
11. Clear existing graph rows for the document before a rebuild to prevent duplicates.
12. For each chunk, create a section node concept from `section_title` or a default section key.
13. Insert extracted entities into `document_entities`, de-duplicating by normalized `entity_name`, `entity_type`, and document.
14. Insert `document_contains_section` relationships using source type `document` and target type `section`.
15. Insert `section_contains_chunk` relationships using section key and chunk ID.
16. Insert `chunk_mentions_entity` relationships for each extracted entity.
17. Insert `entity_related_to_entity` relationships when extraction returns a valid relation.
18. Add `chunk_related_to_chunk` relationships when chunks share strong entity overlap.
19. Return counts for inserted entities and relationships.
20. Add tests for valid extraction, invalid extraction, de-duplication, relationship types, and rebuild behavior.

## 10. Configuration and Environment Variables

```text
SHOPAIKEY_API_KEY
- Purpose: Entity extraction through chat completion.
- Required: Yes if LLM extraction is enabled.
- Example: shopaikey-placeholder
- Scope: Backend-only.

SHOPAIKEY_BASE_URL
- Purpose: OpenAI-compatible API base URL.
- Required: Yes.
- Example: https://api.shopaikey.com/v1
- Scope: Backend-only.

SHOPAIKEY_CHAT_MODEL
- Purpose: Model used for entity extraction.
- Required: Yes if LLM extraction is enabled.
- Example: gpt-5-mini
- Scope: Backend-only.

GRAPH_EXTRACTION_ENABLED
- Purpose: Allows tests or local development to use deterministic fallback.
- Required: No.
- Example: true
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Filters document and chunk rows.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_entity_extraction_service.py tests/test_graph_builder.py -v
```

Manual graph build check:

```text
Upload and process a sample document.
Run graph builder for the document.
Query document_entities for the document_id.
Query document_relationships for the document_id.
```

SQL checks:

```sql
select entity_name, entity_type from document_entities where document_id = '<document_id>';
select relationship_type, count(*) from document_relationships where document_id = '<document_id>' group by relationship_type;
```

Negative checks:

```text
Mock invalid LLM JSON and confirm no malformed rows are inserted.
Build graph for a document with no chunks and expect a clear error.
```

## 12. Acceptance Criteria

- Entity extraction runs for document chunks.
- Extracted entities are validated before persistence.
- `document_entities` rows are created with `user_id = SINGLE_USER_ID`.
- `document_relationships` rows represent document-section-chunk-entity links.
- Relationship weights are numeric and normalized between 0 and 1 where practical.
- Graph build can be rerun without duplicating old rows.
- Invalid LLM JSON is handled safely.
- No community detection, hybrid scoring, or agent logic is added.

## 13. Failure Handling

- Missing document returns a clear not-found error.
- Document with no chunks returns a clear no-chunks error.
- ShopAIKey failure marks extraction failure for the affected chunk and reports it.
- Invalid LLM JSON is rejected by Pydantic validation.
- Database insert failure stops graph build and reports the operation that failed.
- Rebuild failure must not leave duplicate graph rows if rows were cleared first; report partial state if applicable.

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

The report must include counts for entities and relationships produced in a sample or mocked graph build.

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

- Confirm graph level remains medium and does not add community detection.
- Confirm LLM outputs are validated before insert.
- Confirm graph rows are scoped by document and user where schema supports it.
- Confirm extraction prompts do not ask the model to answer user questions.
