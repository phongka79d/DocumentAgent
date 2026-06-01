# Plan.md

# Document QA Agent System Plan

## 1. Project Goal

Build a single-user document question-answering system.

The system allows the user to upload documents, then ask questions about those documents. The backend retrieves relevant evidence using GraphRAG, semantic search, cosine similarity, Top-K retrieval, and scoring. A multi-agent workflow verifies the retrieved evidence and generates a grounded answer.

Example user question:

```text
Tôi có thể làm việc chính thức vào tháng mấy?
```

The final answer must be based only on verified document evidence. The system may perform simple reasoning if the evidence is clear enough.

---

## 2. Tech Stack

### Frontend

```text
React
TypeScript
Tailwind CSS
Axios or TanStack Query
```

### Backend

```text
Python
FastAPI
LangChain
LangGraph
Pydantic
```

### Storage

```text
Supabase Storage
Supabase PostgreSQL
```

### Vector Database

```text
Qdrant Cloud
```

### AI API Provider

```text
ShopAIKey OpenAI-compatible API
```

Use ShopAIKey for:

```text
LLM chat completion
Embeddings
Optional rerank
```

Base URL:

```text
https://api.shopaikey.com/v1
```

Main endpoints:

```text
/chat/completions
/embeddings
/rerank
```

---

## 3. Authentication Policy

This project is for single-user usage.

Do not implement full user authentication or JWT in the MVP.

Use:

```text
SINGLE_USER_ID
```

Backend-only secrets:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
QDRANT_URL
QDRANT_API_KEY
SHOPAIKEY_API_KEY
SHOPAIKEY_BASE_URL=https://api.shopaikey.com/v1
```

Rules:

```text
Never expose Supabase Service Role Key to frontend.
Never expose Qdrant API Key to frontend.
Never expose ShopAIKey API Key to frontend.
All document upload, parsing, embedding, retrieval, and agent execution must go through backend.
```

---

## 4. Supported Document Types

The MVP must support:

```text
PDF
DOCX
TXT
CSV
```

Do not support OCR in the MVP.

OCR can be added later for scanned PDFs and images.

---

## 5. Core Features

### 5.1 Upload Document

The user can upload a document from the frontend.

Backend must:

```text
Validate file type
Store original file in Supabase Storage
Create document metadata in Supabase PostgreSQL
Parse document content
Split content into chunks
Generate embeddings with ShopAIKey embeddings API
Store vectors in Qdrant Cloud
Store chunk metadata in Supabase PostgreSQL
Build medium-level GraphRAG metadata
Write processing logs
```

### 5.2 Document List Page

The user can view uploaded documents.

Each document should show:

```text
Document name
File type
Upload time
Processing status
Chunk count
Error message if processing failed
```

Processing status:

```text
uploaded
processing
ready
failed
```

### 5.3 Chat With Document Page

The user can select one or more documents and ask a question.

Backend must run the LangGraph agent workflow:

```text
Agent 1: Retrieval Agent
Agent 2: Evidence Verification Agent
Agent 3: Answer Generation and Self-Check Agent
```

### 5.4 Evidence Viewer

The user can inspect the evidence used in the final answer.

Each evidence item should show:

```text
File name
Quoted text
Relevance score
Verification status
Reason for acceptance or rejection
```

### 5.5 Agent Logs / Debug Page

The system must keep agent logs for debugging.

Logs should include:

```text
Question
Selected documents
Agent 1 retrieved chunks
Agent 1 scores
Agent 2 verified chunks
Agent 2 rejected chunks
Agent 3 draft answer
Agent 3 self-check result
Final answer
Confidence score
Error messages
Timestamps
```

---

## 6. Data Storage Design

### 6.1 Supabase Storage

Use Supabase Storage for original uploaded files.

Suggested bucket:

```text
documents
```

Suggested object path:

```text
documents/{SINGLE_USER_ID}/{document_id}/{original_filename}
```

---

### 6.2 Supabase PostgreSQL Tables

## Table: documents

Purpose:

```text
Store document-level metadata.
```

Fields:

```text
id UUID primary key
user_id text
file_name text
file_type text
storage_path text
status text
chunk_count integer
created_at timestamp
updated_at timestamp
error_message text nullable
```

---

## Table: document_chunks

Purpose:

```text
Store parsed text chunks and metadata.
```

Fields:

```text
id UUID primary key
document_id UUID
user_id text
chunk_index integer
content text
page_number integer nullable
section_title text nullable
token_count integer
qdrant_point_id text
created_at timestamp
```

---

## Table: document_entities

Purpose:

```text
Store extracted entities for medium-level GraphRAG.
```

Fields:

```text
id UUID primary key
document_id UUID
chunk_id UUID nullable
user_id text
entity_name text
entity_type text
description text nullable
created_at timestamp
```

---

## Table: document_relationships

Purpose:

```text
Store relationships between entities, chunks, sections, and documents.
```

Fields:

```text
id UUID primary key
document_id UUID
source_type text
source_id text
target_type text
target_id text
relationship_type text
weight float
description text nullable
created_at timestamp
```

Example relationship types:

```text
document_contains_section
section_contains_chunk
chunk_mentions_entity
entity_related_to_entity
chunk_related_to_chunk
```

---

## Table: chat_sessions

Purpose:

```text
Store chat sessions.
```

Fields:

```text
id UUID primary key
user_id text
title text
created_at timestamp
updated_at timestamp
```

---

## Table: chat_messages

Purpose:

```text
Store user questions and assistant answers.
```

Fields:

```text
id UUID primary key
session_id UUID
user_id text
role text
content text
created_at timestamp
metadata jsonb
```

---

## Table: agent_runs

Purpose:

```text
Store each full LangGraph execution.
```

Fields:

```text
id UUID primary key
session_id UUID nullable
user_id text
question text
selected_document_ids jsonb
status text
final_answer text nullable
confidence float nullable
created_at timestamp
updated_at timestamp
error_message text nullable
```

---

## Table: agent_steps

Purpose:

```text
Store detailed logs for each agent step.
```

Fields:

```text
id UUID primary key
agent_run_id UUID
step_name text
agent_name text
input jsonb
output jsonb
status text
created_at timestamp
error_message text nullable
```

---

## 7. Qdrant Cloud Design

Collection name:

```text
document_chunks
```

Each Qdrant point should contain:

```text
id: qdrant_point_id
vector: embedding
payload:
  user_id
  document_id
  chunk_id
  file_name
  file_type
  page_number
  section_title
  chunk_index
  content_preview
```

Rules:

```text
Always filter by user_id = SINGLE_USER_ID.
Filter by selected document IDs when the user chooses specific documents.
Do not expose Qdrant directly to frontend.
```

---

## 8. Document Processing Pipeline

### 8.1 Upload Flow

```text
Frontend uploads file
Backend validates file
Backend stores file in Supabase Storage
Backend creates document row with status = uploaded
Backend starts processing
```

---

### 8.2 Parsing Flow

Use different parsers by file type:

```text
PDF  -> PyMuPDF or pypdf
DOCX -> python-docx
TXT  -> plain text reader
CSV  -> pandas or csv module
```

CSV parsing rule:

```text
Convert each row or row group into readable text.
Preserve column names.
Include row index metadata.
```

Example CSV chunk text:

```text
Row 12:
Name: Nguyen Van A
Start Date: 2026-06-01
Probation Period: 2 months
Official Work Date: 2026-08-01
```

---

### 8.3 Chunking Strategy

Use recursive text splitting.

Suggested settings:

```text
chunk_size: 800 to 1200 tokens
chunk_overlap: 100 to 200 tokens
```

Each chunk must preserve:

```text
document_id
file_name
page_number if available
section_title if available
chunk_index
```

---

### 8.4 Embedding Flow

For each chunk:

```text
Call ShopAIKey embeddings endpoint
Receive vector
Store vector in Qdrant Cloud
Store chunk metadata in Supabase
```

Embedding model should be configurable:

```text
SHOPAIKEY_EMBEDDING_MODEL=text-embedding-ada-002
```

Do not hardcode the model in business logic.

---

### 8.5 Medium-Level GraphRAG Construction

GraphRAG level:

```text
Medium
```

The system should build a graph structure:

```text
Document
→ Section
→ Chunk
→ Entity
→ Relationship
```

Required graph features:

```text
Extract important entities from chunks
Link chunks to entities
Link related entities
Link sections to chunks
Allow graph-based retrieval expansion
```

Entity examples:

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
```

Relationship examples:

```text
mentions
contains
requires
starts_at
ends_at
depends_on
related_to
```

GraphRAG does not need community detection in the MVP.

---

## 9. Question Answering Workflow

Use LangGraph to orchestrate the agents.

Main graph:

```text
START
→ Agent 1: Retrieval Agent
→ Agent 2: Evidence Verification Agent
→ Agent 3: Answer Generation Agent
→ Agent 3 Self-Check
→ FINAL
```

If evidence is insufficient:

```text
Agent 2 sets missing_information = true
Agent 3 must answer that the document does not provide enough information
```

---

# 10. Agent 1: Retrieval Agent

## 10.1 Goal

Retrieve the most relevant document chunks for the user question.

Agent 1 must use:

```text
GraphRAG
Semantic Search
Cosine Similarity
Top-K retrieval
Scoring
Optional rerank
```

---

## 10.2 Retrieval Steps

Agent 1 should:

```text
Receive user question
Normalize the question
Extract key terms and entities
Run semantic search in Qdrant
Run graph expansion using extracted entities
Merge semantic and graph candidates
Compute final score
Sort by final score
Return top evidence candidates
```

---

## 10.3 Top-K Settings

Suggested settings:

```text
semantic_top_k = 20
graph_top_k = 20
final_top_k = 8
```

These values must be configurable.

---

## 10.4 Scoring Formula

Use the proposed scoring formula:

```text
final_score =
  0.45 * semantic_similarity
+ 0.25 * graph_relevance
+ 0.15 * keyword_overlap
+ 0.10 * metadata_match
+ 0.05 * recency_or_position_score
```

Score components:

```text
semantic_similarity:
  cosine similarity from Qdrant vector search

graph_relevance:
  score from entity/chunk/relationship match

keyword_overlap:
  overlap between question terms and chunk terms

metadata_match:
  bonus if selected document, page, section, or file metadata is relevant

recency_or_position_score:
  small bonus for more likely important positions, such as title, early policy section, or explicit date field
```

All component scores should be normalized to the range:

```text
0.0 to 1.0
```

---

## 10.5 Optional Rerank

If enabled, Agent 1 can call ShopAIKey rerank endpoint after initial retrieval.

Rerank input:

```text
query: user question
documents: retrieved chunk texts
top_n: final_top_k
```

Rerank must not replace verification.

Rerank only improves candidate ordering.

---

## 10.6 Agent 1 Output Schema

Agent 1 must output structured JSON:

```json
{
  "question": "Tôi có thể làm việc chính thức vào tháng mấy?",
  "candidates": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "file_name": "contract.pdf",
      "content": "Sau 2 tháng thử việc, nhân sự sẽ được xét làm việc chính thức...",
      "page_number": 3,
      "section_title": "Thời gian thử việc",
      "semantic_similarity": 0.88,
      "graph_relevance": 0.76,
      "keyword_overlap": 0.64,
      "metadata_match": 0.7,
      "recency_or_position_score": 0.5,
      "final_score": 0.78,
      "retrieval_reason": "Chunk mentions probation period and official employment condition."
    }
  ]
}
```

---

# 11. Agent 2: Evidence Verification Agent

## 11.1 Goal

Verify whether Agent 1's retrieved chunks are actually useful and reliable for answering the question.

Agent 2 checks:

```text
A. Whether the chunk is relevant to the question
B. Whether the chunk contains enough evidence
C. Whether there are contradictions between chunks
```

---

## 11.2 Verification Rules

Agent 2 must reject chunks that:

```text
Are only loosely related
Do not contain answerable evidence
Are duplicated
Are contradicted by stronger chunks
Contain unclear date or condition without context
Are from the wrong document
```

Agent 2 must accept chunks that:

```text
Directly mention the answer
Provide necessary dates, periods, conditions, or definitions
Support simple reasoning clearly
Help resolve ambiguity
```

---

## 11.3 Missing Information Rule

Agent 2 must set:

```json
"missing_information": true
```

when:

```text
No verified chunk can answer the question
Important date, condition, or context is missing
The answer would require guessing beyond the document
Verified chunks conflict and cannot be resolved
```

---

## 11.4 Agent 2 Output Schema

Agent 2 must output exactly this structure:

```json
{
  "verified_chunks": [],
  "rejected_chunks": [],
  "missing_information": false,
  "confidence": 0.82
}
```

Expanded example:

```json
{
  "verified_chunks": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "file_name": "contract.pdf",
      "quote": "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng.",
      "page_number": 3,
      "verification_reason": "This chunk provides the start date and probation duration needed to infer the official month.",
      "supports_simple_reasoning": true
    }
  ],
  "rejected_chunks": [
    {
      "chunk_id": "uuid",
      "file_name": "contract.pdf",
      "quote": "Nhân sự cần tuân thủ nội quy công ty.",
      "rejection_reason": "This chunk does not mention official work date, start date, or probation duration."
    }
  ],
  "missing_information": false,
  "confidence": 0.82
}
```

---

# 12. Agent 3: Answer Generation and Self-Check Agent

## 12.1 Goal

Generate the final answer using only verified chunks from Agent 2.

Agent 3 may perform simple reasoning if evidence is clear.

Allowed reasoning example:

```text
Start date: 01/06/2026
Probation period: 2 months
Therefore official work month: 08/2026
```

Not allowed:

```text
Guessing a month without evidence
Using outside knowledge
Using rejected chunks
Inventing dates, policies, or conditions
```

---

## 12.2 Answer Style

The final answer should be:

```text
Clear
Short
Direct
Grounded in evidence
Written in Vietnamese by default
```

---

## 12.3 Citation Style

Use citation style:

```text
File name + quoted text
```

Example:

```text
Bạn có thể làm việc chính thức vào tháng 8/2026.

Căn cứ:
- contract.pdf: "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng."
```

Do not show internal chunk ID to normal users.

Chunk ID can be shown only in Agent Logs / Debug Page.

---

## 12.4 Insufficient Evidence Answer

If Agent 2 returns:

```json
"missing_information": true
```

Agent 3 must answer:

```text
Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.
```

Then explain what is missing.

Example:

```text
Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định tháng bạn có thể làm việc chính thức.

Thông tin còn thiếu:
- Ngày bắt đầu làm việc hoặc thử việc.
- Thời gian thử việc.
- Điều kiện để chuyển sang làm việc chính thức.
```

---

## 12.5 Self-Check

Before final output, Agent 3 must check:

```text
Does the answer use only verified chunks?
Does the answer avoid rejected chunks?
Does the answer include citation?
Does the reasoning follow clearly from the evidence?
Does the answer avoid unsupported claims?
Is the answer understandable to the user?
```

---

## 12.6 Agent 3 Output Schema

```json
{
  "final_answer": "Bạn có thể làm việc chính thức vào tháng 8/2026...",
  "citations": [
    {
      "file_name": "contract.pdf",
      "quote": "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng."
    }
  ],
  "reasoning_summary": "Start date is 01/06/2026 and probation lasts 2 months, so the official month is 08/2026.",
  "confidence": 0.82,
  "self_check": {
    "uses_only_verified_chunks": true,
    "has_citation": true,
    "has_unsupported_claims": false,
    "is_ready": true
  }
}
```

---

# 13. Backend API Design

## 13.1 Upload Document

```text
POST /api/documents/upload
```

Request:

```text
multipart/form-data
file
```

Response:

```json
{
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "status": "uploaded"
}
```

---

## 13.2 List Documents

```text
GET /api/documents
```

Response:

```json
{
  "documents": [
    {
      "id": "uuid",
      "file_name": "contract.pdf",
      "file_type": "pdf",
      "status": "ready",
      "chunk_count": 42,
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

---

## 13.3 Get Document Detail

```text
GET /api/documents/{document_id}
```

Response:

```json
{
  "id": "uuid",
  "file_name": "contract.pdf",
  "status": "ready",
  "chunk_count": 42,
  "chunks": []
}
```

---

## 13.4 Ask Question

```text
POST /api/chat/ask
```

Request:

```json
{
  "session_id": "uuid",
  "question": "Tôi có thể làm việc chính thức vào tháng mấy?",
  "document_ids": ["uuid"]
}
```

Response:

```json
{
  "answer": "Bạn có thể làm việc chính thức vào tháng 8/2026...",
  "confidence": 0.82,
  "citations": [
    {
      "file_name": "contract.pdf",
      "quote": "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng."
    }
  ],
  "agent_run_id": "uuid"
}
```

---

## 13.5 Get Evidence

```text
GET /api/agent-runs/{agent_run_id}/evidence
```

Response:

```json
{
  "verified_chunks": [],
  "rejected_chunks": []
}
```

---

## 13.6 Get Agent Logs

```text
GET /api/agent-runs/{agent_run_id}/logs
```

Response:

```json
{
  "agent_run_id": "uuid",
  "steps": [
    {
      "agent_name": "retrieval_agent",
      "input": {},
      "output": {},
      "status": "success",
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

---

# 14. Frontend Page Plan

## 14.1 Upload Document Page

Features:

```text
Drag and drop upload
File type validation
Upload progress
Processing status
Error display
```

---

## 14.2 Document List Page

Features:

```text
Show all uploaded documents
Show processing status
Select document for chat
Delete document if needed
Refresh status
```

---

## 14.3 Chat With Document Page

Features:

```text
Select document
Ask question
Show assistant answer
Show confidence
Show citations
Open evidence viewer
```

---

## 14.4 Evidence Viewer

Features:

```text
Show verified chunks
Show rejected chunks
Show file name
Show quote
Show verification reason
Show score
```

---

## 14.5 Agent Logs / Debug Page

Features:

```text
Show each agent step
Show raw JSON input and output
Show retrieval scores
Show verification result
Show self-check result
Show errors
```

---

# 15. Environment Variables

Backend `.env`:

```text
APP_ENV=development

SINGLE_USER_ID=single_user

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=documents

QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION=document_chunks

SHOPAIKEY_API_KEY=
SHOPAIKEY_BASE_URL=https://api.shopaikey.com/v1
SHOPAIKEY_CHAT_MODEL=gpt-5-mini
SHOPAIKEY_EMBEDDING_MODEL=text-embedding-ada-002
SHOPAIKEY_RERANK_MODEL=rerank-english-v2.0

RETRIEVAL_SEMANTIC_TOP_K=20
RETRIEVAL_GRAPH_TOP_K=20
RETRIEVAL_FINAL_TOP_K=8
ENABLE_RERANK=true
```

Frontend `.env`:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Frontend must not contain private API keys.

---

# 16. Suggested Project Structure

```text
project-root/
  backend/
    app/
      main.py
      core/
        config.py
        logging.py
      api/
        documents.py
        chat.py
        agent_runs.py
      services/
        supabase_service.py
        qdrant_service.py
        shopaikey_service.py
        document_parser.py
        chunking_service.py
        embedding_service.py
        graph_builder.py
      agents/
        graph.py
        retrieval_agent.py
        verification_agent.py
        answer_agent.py
        schemas.py
      db/
        models.py
        migrations/
      utils/
        scoring.py
        text.py
    requirements.txt
    .env.example

  frontend/
    src/
      api/
        client.ts
        documents.ts
        chat.ts
        agentRuns.ts
      pages/
        UploadDocumentPage.tsx
        DocumentListPage.tsx
        ChatPage.tsx
        EvidenceViewerPage.tsx
        AgentLogsPage.tsx
      components/
        DocumentCard.tsx
        UploadBox.tsx
        ChatBox.tsx
        EvidencePanel.tsx
        AgentLogViewer.tsx
      App.tsx
      main.tsx
    package.json
    .env.example

  docs/
    Plan.md

  README.md
```

---

# 17. Implementation Phases

## Phase 1: Backend Foundation

Tasks:

```text
Create FastAPI backend
Create config system
Connect Supabase
Connect Qdrant Cloud
Connect ShopAIKey chat API
Connect ShopAIKey embeddings API
Create health check endpoint
```

Acceptance criteria:

```text
Backend starts successfully
Environment variables load correctly
Health check returns ok
Supabase connection works
Qdrant connection works
ShopAIKey test request works
```

---

## Phase 2: Document Upload and Storage

Tasks:

```text
Implement document upload endpoint
Validate PDF, DOCX, TXT, CSV
Store original file in Supabase Storage
Create document metadata row
Show document status
```

Acceptance criteria:

```text
User can upload supported files
File appears in Supabase Storage
Document row appears in Supabase PostgreSQL
Unsupported file types are rejected
```

---

## Phase 3: Parsing and Chunking

Tasks:

```text
Implement PDF parser
Implement DOCX parser
Implement TXT parser
Implement CSV parser
Implement chunking service
Store chunks in Supabase
```

Acceptance criteria:

```text
PDF text is extracted
DOCX text is extracted
TXT text is extracted
CSV rows are converted into readable text
Chunks are created with metadata
```

---

## Phase 4: Embeddings and Qdrant Indexing

Tasks:

```text
Generate embeddings using ShopAIKey
Create Qdrant collection if missing
Store vectors in Qdrant Cloud
Link Qdrant point IDs to chunk rows
```

Acceptance criteria:

```text
Each chunk has an embedding
Each vector is stored in Qdrant
Each chunk has a qdrant_point_id
Vector search returns relevant chunks
```

---

## Phase 5: Medium GraphRAG

Tasks:

```text
Extract entities from chunks
Create document-section-chunk-entity graph
Store entities and relationships in Supabase
Implement graph expansion retrieval
```

Acceptance criteria:

```text
Entities are extracted
Relationships are stored
Graph retrieval can find related chunks
Graph score can be calculated
```

---

## Phase 6: Agent 1 Retrieval

Tasks:

```text
Implement semantic search
Implement graph search
Implement keyword overlap score
Implement metadata match score
Implement final scoring formula
Implement Top-K selection
Optionally implement rerank
```

Acceptance criteria:

```text
Agent 1 returns structured candidate chunks
Scores are visible in logs
Top-K results are sorted by final_score
```

---

## Phase 7: Agent 2 Evidence Verification

Tasks:

```text
Implement verification prompt
Validate Agent 2 JSON output with Pydantic
Verify relevance
Verify sufficiency
Check contradiction
Return verified and rejected chunks
```

Acceptance criteria:

```text
Agent 2 returns verified_chunks
Agent 2 returns rejected_chunks
Agent 2 sets missing_information correctly
Agent 2 confidence is between 0 and 1
```

---

## Phase 8: Agent 3 Answer and Self-Check

Tasks:

```text
Generate answer from verified chunks only
Add file name + quote citations
Allow simple reasoning only when evidence is clear
Run self-check before final response
Return final structured output
```

Acceptance criteria:

```text
Answer uses only verified chunks
Answer includes citations
Answer does not use rejected chunks
Self-check result is stored
Insufficient evidence case is handled safely
```

---

## Phase 9: LangGraph Orchestration

Tasks:

```text
Create LangGraph workflow
Connect Agent 1, Agent 2, Agent 3
Persist each step into agent_steps
Persist final result into agent_runs
Handle errors
```

Acceptance criteria:

```text
One question triggers the full graph
Each agent step is logged
Final answer is returned to frontend
Errors are visible in logs
```

---

## Phase 10: Frontend UI

Tasks:

```text
Build Upload Document Page
Build Document List Page
Build Chat With Document Page
Build Evidence Viewer
Build Agent Logs / Debug Page
```

Acceptance criteria:

```text
User can upload documents
User can view uploaded documents
User can ask questions
User can view citations
User can inspect evidence
User can inspect agent logs
```

---

# 18. Quality Rules

## 18.1 Grounding Rule

The final answer must be grounded in verified chunks.

Agent 3 must not use:

```text
Unverified chunks
Rejected chunks
Outside knowledge
Unsupported assumptions
```

---

## 18.2 Simple Reasoning Rule

Simple reasoning is allowed only when the evidence clearly supports it.

Allowed:

```text
Adding a probation duration to a start date
Comparing dates
Extracting a month from a date
Summarizing a clearly stated policy
```

Not allowed:

```text
Guessing missing dates
Assuming company policy
Inferring hidden conditions
Inventing document content
```

---

## 18.3 Citation Rule

Every final answer must include citations.

Citation format:

```text
file_name: "quoted text"
```

---

## 18.4 Missing Information Rule

If evidence is insufficient, the system must say so clearly.

Do not force an answer.

---

## 18.5 Debuggability Rule

Every agent run must be traceable.

The developer must be able to inspect:

```text
What chunks were retrieved
Why chunks were selected
Why chunks were rejected
What verified chunks were used
How the final answer was generated
Whether self-check passed
```

---

# 19. MVP Success Criteria

The MVP is successful when:

```text
User can upload PDF, DOCX, TXT, and CSV files
Files are stored in Supabase Storage
Document metadata and chunks are stored in Supabase PostgreSQL
Chunk embeddings are stored in Qdrant Cloud
User can ask a question about uploaded documents
Agent 1 retrieves and scores candidate chunks
Agent 2 verifies evidence
Agent 3 generates a grounded answer with citations
Agent 3 self-checks the answer before output
Frontend displays answer, evidence, and agent logs
No Auth/JWT is required
All private keys remain backend-only
```

---

# 20. Initial Test Scenario

Upload a document containing:

```text
Người lao động bắt đầu thử việc từ ngày 01/06/2026.
Thời gian thử việc kéo dài 2 tháng.
Sau khi hoàn thành thử việc, người lao động có thể được xét làm việc chính thức.
```

Ask:

```text
Tôi có thể làm việc chính thức vào tháng mấy?
```

Expected retrieval:

```text
Chunks mentioning start date, probation duration, and official work condition.
```

Expected reasoning:

```text
01/06/2026 + 2 months = 01/08/2026
```

Expected answer:

```text
Bạn có thể được xét làm việc chính thức vào tháng 8/2026.

Căn cứ:
- file_name: "Người lao động bắt đầu thử việc từ ngày 01/06/2026."
- file_name: "Thời gian thử việc kéo dài 2 tháng."
- file_name: "Sau khi hoàn thành thử việc, người lao động có thể được xét làm việc chính thức."
```

---

# 21. Non-Goals for MVP

Do not implement these in the MVP:

```text
Multi-user authentication
JWT login system
OCR for scanned documents
Payment system
Admin dashboard
Complex permission system
Full Microsoft GraphRAG community detection
Fine-tuning
Mobile app
Browser extension
```

---

# 22. Future Improvements

Possible future improvements:

```text
OCR support
Multi-user auth
Better graph visualization
Hybrid BM25 + vector search
Advanced reranking
Streaming answers
Document comparison
Conversation memory
Source page preview
Automatic summary per document
Export answer to PDF or DOCX
```
