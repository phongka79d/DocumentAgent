# Live RAG Evaluation Report

Date: 2026-06-17  
Evaluator role: Senior RAG QA Engineer and Evaluator  
Project: DocumentAgent  
Backend tested: FastAPI on `http://127.0.0.1:8001`  
Live dependencies used: Supabase database/storage, Qdrant, ShopAIKey embeddings/chat calls

## Executive Summary

The RAG pipeline is functional and has strong safety boundaries around grounding, citation validation, and insufficient-evidence fallback behavior. The workflow persisted full `agent_runs` and `agent_steps` records for every live test, and the answer layer generally avoided hallucinating when evidence was weak or unavailable.

The main quality issues are retrieval precision and answer completion for simple reasoning. Retrieval returned many loosely related chunks for simple questions. A chronology question had enough verified evidence, but the answer agent failed self-check and returned a fallback instead of answering. A separate confidence bug caused a grounded direct answer to return public `confidence: 0.0`.

Overall status: usable MVP with good safety posture, but not yet reliable enough for high-confidence QA because retrieval noise and reasoning fallback can prevent answer delivery.

## System Under Test

### Primary RAG Flow

`POST /api/chat/ask` follows this path:

1. `backend/app/api/chat.py`
   - Validates `ChatAskRequest`.
   - Persists user message through `chat_service.prepare_chat_persistence`.
   - Calls `run_qa_workflow`.

2. `backend/app/agents/graph.py`
   - Creates an `agent_run`.
   - Runs Agent 1 retrieval.
   - Runs Agent 2 verification.
   - Runs Agent 3 answer generation and self-check.
   - Marks the agent run success or failure.

3. `backend/app/agents/retrieval_agent.py`
   - Calls hybrid retrieval.
   - Expands adjacent context.
   - Logs Agent 1 output to `agent_steps`.

4. `backend/app/agents/verification_agent.py`
   - Validates retrieved candidates.
   - Verifies quote support.
   - Runs evidence coverage review.
   - Applies missing-information adjustments.
   - Logs Agent 2 output to `agent_steps`.

5. `backend/app/agents/answer_agent.py`
   - Generates an answer using verified chunks only.
   - Validates citations against verified evidence.
   - Runs grounding self-check.
   - Returns final answer or deterministic fallback.

### Live Data Used

Document:

- `file_name`: `alice-in-wonderland.txt`
- `document_id`: `c90c48f9-0e3c-4d2c-9464-31594ae85820`
- `status`: `ready`
- `chunk_count`: `35`

I did not upload a new document during this audit. I used the existing indexed live document to avoid nondeterminism from background document processing and indexing.

## Live Test Log

### Service Discovery and Setup

Initial sandboxed backend probes:

```text
GET http://127.0.0.1:8000/api/health -> connection/client-side failure
GET http://127.0.0.1:8005/api/health -> unable to connect
GET http://127.0.0.1:8080/api/health -> unable to connect
```

The first local backend process could start, but sandboxed network access caused Supabase failures:

```text
SupabaseConnectionError: Supabase operation 'document metadata list' failed: ConnectError.
[WinError 10061] No connection could be made because the target machine actively refused it
```

After running the backend with approved network access on port `8001`:

```text
GET http://127.0.0.1:8001/api/health
-> {"status":"ok","service":"document-qa-agent","app_env":"development"}
```

Document inventory:

```text
GET http://127.0.0.1:8001/api/documents
-> alice-in-wonderland.txt, ready, 35 chunks
```

Direct Supabase read also confirmed:

```text
rows 1
[{'id': 'c90c48f9-0e3c-4d2c-9464-31594ae85820',
  'file_name': 'alice-in-wonderland.txt',
  'status': 'ready',
  'chunk_count': 35}]
```

### Test Case 1: Direct Answer

Question:

```text
What animal does Alice see before she runs across the field?
```

API:

```text
POST /api/chat/ask
document_ids = ["c90c48f9-0e3c-4d2c-9464-31594ae85820"]
```

Response:

```json
{
  "answer": "Alice thấy một con thỏ trước khi cô chạy qua cánh đồng.",
  "confidence": 0.0,
  "citations": [
    {
      "file_name": "alice-in-wonderland.txt",
      "quote": "Alice started to her feet, for it flashed across her mind that she had never before seen a rabbit with either a waistcoat-pocket, or a watch to take out of it, and burning with curiosity, she ran across the field after it,"
    }
  ],
  "agent_run_id": "ac1640f9-f44e-4774-9352-f8343a3cf836"
}
```

Persisted DB/API evidence:

- `agent_runs.status`: `success`
- Agent steps persisted:
  - `agent_1_retrieval`: success
  - `agent_2_verification`: success
  - `agent_3_answer_self_check`: success
- Retrieval candidates: `13`
- Verified chunks: `1`
- Rejected chunks: `1`
- Agent 2 confidence: `0.9`
- Agent 3 grounding confidence: `1.0`
- Public response confidence: `0.0`

Important verified quote:

```text
alice-in-wonderland.txt: "Alice started to her feet, for it flashed across her mind that she had never before seen a rabbit with either a waistcoat-pocket, or a watch to take out of it, and burning with curiosity, she ran across the field after it,"
```

Finding:

The answer is faithful and relevant. The quote supports the answer. The public confidence is wrong or at least misleading because the draft answer returned `confidence: 0.0`, and `answer_agent.py` uses the minimum of draft, verification, and grounding confidence.

### Test Case 2: Simple Chronology Reasoning

Question:

```text
Which happened first: Alice saw the White Rabbit, or Alice fell down the rabbit-hole?
```

API:

```text
POST /api/chat/ask
document_ids = ["c90c48f9-0e3c-4d2c-9464-31594ae85820"]
```

Response:

```json
{
  "answer": "Hệ thống chưa thể hoàn tất tự kiểm tra câu trả lời, nhưng tài liệu có các bằng chứng liên quan ở phần trích dẫn.",
  "confidence": 0.0,
  "citations": [
    {
      "file_name": "alice-in-wonderland.txt",
      "quote": "So she was considering in her own mind (as well as she could, for the hot day made her feel very sleepy and stupid), whether the pleasure of making a daisy-chain would be worth the trouble of getting up and picking the daisies, when suddenly a White Rabbit with pink eyes ran close by her."
    },
    {
      "file_name": "alice-in-wonderland.txt",
      "quote": "I almost wish I hadn't gone down that rabbit-hole"
    },
    {
      "file_name": "alice-in-wonderland.txt",
      "quote": "down she came upon a heap of sticks and dry leaves, and the fall was over."
    }
  ],
  "agent_run_id": "e9938305-9f1e-4b43-b372-e8d32e8d0aa8"
}
```

Persisted DB/API evidence:

- `agent_runs.status`: `success`
- Agent steps persisted:
  - `agent_1_retrieval`: success
  - `agent_2_verification`: success
  - `agent_3_answer_self_check`: success
- Retrieval candidates: `13`
- Verified chunks: `3`
- Rejected chunks: `1`
- Agent 2 `missing_information`: `false`
- Agent 2 confidence: `0.0`
- Agent 3 `fallback_reason`: `self_check_failed`
- Agent 3 `self_check_result.is_ready`: `false`

Verified quotes:

```text
alice-in-wonderland.txt: "So she was considering in her own mind (as well as she could, for the hot day made her feel very sleepy and stupid), whether the pleasure of making a daisy-chain would be worth the trouble of getting up and picking the daisies, when suddenly a White Rabbit with pink eyes ran close by her."

alice-in-wonderland.txt: "I almost wish I hadn't gone down that rabbit-hole"

alice-in-wonderland.txt: "down she came upon a heap of sticks and dry leaves, and the fall was over."
```

Finding:

The retriever and verifier found enough evidence to answer that Alice saw the White Rabbit first. The system did not hallucinate, but it failed to answer the user's direct comparison question. This is a simple reasoning failure, not a retrieval recall failure.

### Test Case 3: Missing Information

Question:

```text
What is Alice's bank account number?
```

API:

```text
POST /api/chat/ask
document_ids = ["c90c48f9-0e3c-4d2c-9464-31594ae85820"]
```

Response:

```json
{
  "answer": "Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.\n\nThông tin còn thiếu:\n- Bằng chứng đã được xác minh trực tiếp trả lời câu hỏi.\n- Ngữ cảnh, ngày tháng, điều kiện hoặc dữ kiện cần thiết để suy luận.",
  "confidence": 0.0,
  "citations": [],
  "agent_run_id": "d0f8c9a4-ad3e-4405-8dbe-b8850f7778eb"
}
```

Persisted DB/API evidence:

- `agent_runs.status`: `success`
- Agent steps persisted:
  - `agent_1_retrieval`: success
  - `agent_2_verification`: success
  - `agent_3_answer_self_check`: success
- Retrieval candidates: `14`
- Verified chunks: `0`
- Rejected chunks: `8`
- Agent 3 `fallback_reason`: `insufficient_evidence`
- Agent 3 `self_check_result.is_ready`: `false`
- Agent 3 `self_check_result.has_citation`: `false`

Finding:

This behavior satisfies the missing-information rule. The system did not guess, did not cite irrelevant evidence as support, and returned the predefined insufficient-evidence answer.

## Metric Evaluation Table

| Metric | Score | Impacting Files | Key Findings and Evidence |
|---|---:|---|---|
| Faithfulness / Groundedness | 8/10 | `backend/app/agents/answer_agent.py`, `backend/app/services/answer_evidence_service.py`, `backend/app/agents/verification_agent.py`, `backend/app/agents/prompts.py` | Direct answer was derived from the verified quote. The unanswerable question avoided hallucination. The sequence question failed safe instead of making an unsupported answer. Deduction: confidence handling is misleading, and self-check fallback answer is not a real answer despite evidence being available. |
| Answer Relevance | 7/10 | `backend/app/agents/answer_agent.py`, `backend/app/services/answer_prompt_service.py`, `backend/app/agents/prompts.py` | Direct answer directly answered the question. Missing-info response addressed insufficiency. Sequence question returned a generic self-check fallback instead of answering which event happened first. |
| Context Precision | 4/10 | `backend/app/services/hybrid_retrieval_service.py`, `backend/app/services/retrieval_context_service.py`, `backend/app/agents/retrieval_agent.py`, `backend/app/core/config.py` | Retrieval returned 13-14 candidates with substantial noise. For the direct rabbit question, top candidates included garden, tea party, chimney, Queen, and other unrelated chunks before/around the useful evidence. |
| Context Recall | 8/10 | `backend/app/services/retrieval_service.py`, `backend/app/services/hybrid_retrieval_service.py`, `backend/app/services/retrieval_context_service.py`, `backend/app/agents/retrieval_agent.py` | Required evidence was retrieved for the direct answer and chronology question. Missing-info test had no verified evidence, as expected. Deduction: recall succeeded, but downstream reasoning did not use the recalled evidence to answer chronology. |
| Citation Rule | 7/10 | `backend/app/services/answer_evidence_service.py`, `backend/app/schemas/chat.py`, `frontend/src/components/AnswerPanel.tsx` | API returns structured citations with `file_name` and exact `quote`. Raw chunk IDs are hidden from final answer/citations. Backend has `format_citation()` that renders `file_name: "quote"`. Deduction: frontend displays file and blockquote separately, not the exact MVP string format. |
| Simple Reasoning Rule | 6/10 | `backend/app/agents/answer_agent.py`, `backend/app/agents/verification_agent.py`, `backend/app/agents/prompts.py` | The system avoids unsupported reasoning. However, a simple chronology question failed even with verified evidence. It returned a self-check fallback instead of inferring order from quote/chunk sequence. |
| Missing Information Rule | 9/10 | `backend/app/agents/answer_agent.py`, `backend/app/services/verification_post_processor.py`, `backend/app/agents/verification_agent.py` | Missing bank-account question correctly returned the predefined insufficient-evidence answer with missing details, no citations, no guessing, and `confidence: 0.0`. Minor deduction: the missing-details text is generic rather than tailored to "bank account number". |

## File-Level Findings

### 1. Public confidence can be wrong for grounded answers

Impacted file:

- `backend/app/agents/answer_agent.py`

Relevant behavior:

```text
final confidence = min(draft_output.confidence, verification.confidence, grounding.confidence)
```

Live evidence:

- Direct answer:
  - Agent 2 verification confidence: `0.9`
  - Grounding review confidence: `1.0`
  - Draft answer confidence: `0.0`
  - Public response confidence: `0.0`
  - Self-check ready: `true`

Why this matters:

A fully grounded and self-check-passing answer is displayed as zero confidence. This damages user trust and can make downstream evaluations look worse than the actual grounding quality.

Recommendation:

- Validate provider-supplied draft confidence.
- Treat missing or zero draft confidence as untrusted metadata, not as a hard cap.
- Consider deriving final confidence from verifier confidence and grounding confidence when the answer passes all evidence checks.

### 2. Retrieval precision is low

Impacted files:

- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/retrieval_context_service.py`
- `backend/app/agents/retrieval_agent.py`
- `backend/app/core/config.py`

Live evidence:

Direct rabbit question:

- Retrieved candidates: `13`
- Verified chunks: `1`
- Rejected chunks after verification: `1`
- Top retrieved candidates included unrelated scenes such as garden, tea party, chimney, Queen, and trial content.

Missing bank-account question:

- Retrieved candidates: `14`
- Verified chunks: `0`
- Rejected chunks: `8`

Why this matters:

Low precision increases LLM verification cost, increases latency, and raises the probability of selecting misleading context.

Recommendation:

- Add a relevance threshold before context expansion.
- Consider enabling reranking if `SHOPAIKEY_RERANK_MODEL` is available.
- Penalize generic entity-only graph matches for broad entities like `Alice`.
- Tune `retrieval_final_top_k` and `retrieval_context_max_candidates`.

### 3. Simple chronology reasoning fails despite available evidence

Impacted files:

- `backend/app/agents/answer_agent.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/verification_agent.py`

Live evidence:

Chronology question verified these quotes:

```text
White Rabbit appears close by Alice.
Alice later says she had gone down the rabbit-hole.
The fall was over.
```

The system returned:

```text
Hệ thống chưa thể hoàn tất tự kiểm tra câu trả lời...
```

Why this matters:

This is an MVP-level reasoning case. The system had enough evidence, but answer generation/self-check failed to produce a final answer.

Recommendation:

- Add deterministic handling for chronology questions using `chunk_index` and quote order.
- Mark ordering comparisons as supported simple reasoning when verified chunks provide ordered source positions.
- Improve self-check retry instructions for comparison/order questions.
- Log the failed draft answer for internal debugging if safe to persist.

### 4. Citation format is structurally correct but not displayed in exact MVP format

Impacted files:

- `backend/app/services/answer_evidence_service.py`
- `frontend/src/components/AnswerPanel.tsx`

Backend helper:

```text
format_citation(citation) -> file_name: "quote"
```

Frontend behavior:

```tsx
<p>{citation.file_name}</p>
<blockquote>{citation.quote}</blockquote>
```

Why this matters:

The MVP rule asks for exact format:

```text
file_name: "quoted text"
```

The API provides the necessary fields and hides raw IDs, but the visible UI does not render the exact required string.

Recommendation:

- Render citation as a single visible string:

```text
alice-in-wonderland.txt: "Alice started to her feet..."
```

### 5. Missing-information behavior is strong but missing details are generic

Impacted files:

- `backend/app/agents/answer_agent.py`
- `backend/app/services/verification_post_processor.py`

Live evidence:

Question:

```text
What is Alice's bank account number?
```

Answer:

```text
Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.

Thông tin còn thiếu:
- Bằng chứng đã được xác minh trực tiếp trả lời câu hỏi.
- Ngữ cảnh, ngày tháng, điều kiện hoặc dữ kiện cần thiết để suy luận.
```

Why this matters:

The safety behavior is correct. However, the missing detail does not specifically say that the missing item is Alice's bank account number.

Recommendation:

- Keep the exact predefined safety response if product requirements require it.
- If allowed, append a structured missing field derived from the question, for example: `Missing: Alice's bank account number`.

## Detailed Metric Reasoning

### Faithfulness: 8/10

Strengths:

- Agent 3 receives only verified chunks through `answer_prompt_service.answer_evidence_payload`.
- Citations are validated against verified evidence in `answer_evidence_service.validate_answer_evidence_contract`.
- Rejected evidence is blocked from visible answer text.
- The unanswerable question returned a safe fallback instead of hallucinating.

Weaknesses:

- Direct answer confidence was `0.0` despite full grounding.
- The fallback for self-check failure is safe but not a faithful answer to the user's question; it only says evidence exists.

### Answer Relevance: 7/10

Strengths:

- Direct answer was concise and on-topic.
- Missing-information answer was appropriate for unavailable data.

Weaknesses:

- The chronology question did not receive the requested comparison answer.
- The self-check fallback is operationally honest but not semantically relevant enough for a user asking a direct question.

### Context Precision: 4/10

Strengths:

- The verifier filters noisy retrieved chunks before answer generation.
- Context expansion helps recall.

Weaknesses:

- Hybrid retrieval over-selects broad Alice-related chunks.
- Graph matches around `Alice` appear to boost unrelated content.
- Adjacent context expansion adds more chunks, but not always relevant ones.

### Context Recall: 8/10

Strengths:

- Direct answer evidence was present.
- Chronology evidence was present.
- Missing-information case correctly ended with no verified chunks.

Weaknesses:

- The final pipeline did not convert recalled chronology evidence into an answer.

### Citation Rule: 7/10

Strengths:

- API citations have exact verified quotes.
- Raw `chunk_id` values are not shown in final answer/citations.
- Backend has the exact formatter required by the rule.

Weaknesses:

- Frontend does not render the citation in exact `file_name: "quoted text"` format.
- Missing-information responses intentionally have no citations, which is acceptable only when no answer is provided.

### Simple Reasoning Rule: 6/10

Strengths:

- The system is conservative and refuses unsafe reasoning.
- Prompts explicitly restrict reasoning to supported simple inferences.

Weaknesses:

- Chronological ordering failed.
- Agent 2 returned `missing_information: false` but `confidence: 0.0`, an internally inconsistent signal for downstream answer generation.

### Missing Information Rule: 9/10

Strengths:

- Exact insufficient-evidence fallback path triggered.
- No citations were returned for an answer that could not be supported.
- No outside assumptions were made.

Weaknesses:

- Missing details are generic rather than question-specific.

## Recommendations by Priority

### Priority 1: Fix confidence calibration

File:

- `backend/app/agents/answer_agent.py`

Change:

- Do not blindly cap final confidence by LLM draft confidence.
- If self-check is ready and grounding confidence is high, derive public confidence from verifier and grounding confidence.

Expected impact:

- Improves user trust and evaluation accuracy.

### Priority 2: Add deterministic chronology support

Files:

- `backend/app/agents/answer_agent.py`
- `backend/app/agents/verification_agent.py`
- `backend/app/agents/schemas.py`

Change:

- Preserve `chunk_index` or source order in verified evidence passed to Agent 3.
- For questions containing "which happened first", compare source positions when quotes are from the same document.
- Mark the inference as simple reasoning when evidence order supports it.

Expected impact:

- Fixes an MVP-level reasoning failure.

### Priority 3: Improve retrieval precision

Files:

- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/retrieval_context_service.py`
- `backend/app/core/config.py`

Change:

- Add minimum final-score threshold.
- Reduce graph weight for broad entity matches.
- Enable or tune reranking.
- Limit adjacent context expansion to cases where anchor score is strong enough.

Expected impact:

- Fewer irrelevant chunks, lower LLM cost, faster verification, better context precision.

### Priority 4: Render exact citation format in UI

File:

- `frontend/src/components/AnswerPanel.tsx`

Change:

- Replace separate file and blockquote display with a visible formatted citation string:

```tsx
{citation.file_name}: "{citation.quote}"
```

Expected impact:

- Satisfies the MVP citation rule exactly.

### Priority 5: Make missing details more specific if product rules allow

File:

- `backend/app/agents/answer_agent.py`

Change:

- Keep the predefined safety response but optionally include the missing target from the question.

Expected impact:

- Better user clarity while preserving safety.

## Final Assessment

The implementation is safety-first and has good multi-agent logging and evidence inspection. The strongest parts are quote validation, rejected-evidence blocking, missing-information fallback, and persisted audit traces.

The weakest parts are retrieval precision, confidence calibration, and simple reasoning completion. The system often has enough evidence, but noisy retrieval and conservative self-check behavior can prevent a useful final answer.

Recommended overall score for MVP RAG quality: 7/10.
