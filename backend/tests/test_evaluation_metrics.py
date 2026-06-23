from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from app.evaluation.dataset import (
    DEFAULT_FIXTURE_DIRECTORY,
    EvaluationDatasetError,
    load_dataset,
)
from app.evaluation.metrics import (
    DEFAULT_THRESHOLDS,
    answer_term_coverage,
    calculate_metrics,
    citation_validity_rate,
    evaluate_thresholds,
    forbidden_term_rate,
    grounding_pass_rate,
    no_result_rate,
    precision_at_k,
    recall_at_k,
    rerank_lift,
    unexpected_no_result_rate,
)
from app.evaluation.runner import run_evaluation, write_report
from app.models.schemas import DocumentResponse
from scripts import run_rag_evaluation as evaluation_script
from scripts import seed_evaluation_corpus as seed_script


DATASET_PATH = Path("evaluation/datasets/phase3_v1.jsonl")
DOCUMENT_ID = UUID("12345678-1234-4234-8234-123456789abc")


def _document(status: str = "ready") -> DocumentResponse:
    return DocumentResponse(
        id=DOCUMENT_ID,
        title="Leave Policy",
        file_name="leave_policy.md",
        mime_type="text/markdown",
        file_size=12,
        file_hash="abc",
        storage_path=f"documents/{DOCUMENT_ID}/original/leave_policy.md",
        status=status,
    )


def test_versioned_dataset_validates_and_covers_required_scenarios():
    cases = load_dataset(DATASET_PATH)

    assert len(cases) >= 12
    assert len({case.case_id for case in cases}) == len(cases)
    assert all(
        set(case.model_dump())
        == {
            "case_id",
            "question",
            "document_titles",
            "expected_chunk_contains",
            "required_answer_terms",
            "forbidden_answer_terms",
            "expected_no_result",
            "filters",
            "tags",
        }
        for case in cases
    )
    tags = {tag for case in cases for tag in case.tags}
    assert {
        "semantic-paraphrase",
        "exact-keyword",
        "mime",
        "heading",
        "section",
        "page",
        "decomposition",
        "comparison",
        "relation-aware",
        "citation-selection",
        "insufficient-context",
        "conflict",
    } <= tags
    assert all(path.suffix == ".md" for path in DEFAULT_FIXTURE_DIRECTORY.iterdir())


def test_dataset_rejects_duplicate_case_ids(tmp_path: Path):
    row = json.loads(DATASET_PATH.read_text(encoding="utf-8").splitlines()[0])
    path = tmp_path / "duplicate.jsonl"
    path.write_text("\n".join([json.dumps(row), json.dumps(row)]), encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="Duplicate case IDs"):
        load_dataset(path)


def test_dataset_rejects_invalid_jsonl_syntax(tmp_path: Path):
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"case_id":', encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="Invalid JSON at line 1"):
        load_dataset(path)


def test_dataset_rejects_unknown_fixture_title(tmp_path: Path):
    row = json.loads(DATASET_PATH.read_text(encoding="utf-8").splitlines()[0])
    row["document_titles"] = ["Unknown Policy"]
    path = tmp_path / "unknown.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="unknown titles"):
        load_dataset(path)


def test_dataset_rejects_positive_case_without_evidence(tmp_path: Path):
    row = json.loads(DATASET_PATH.read_text(encoding="utf-8").splitlines()[0])
    row["expected_chunk_contains"] = []
    path = tmp_path / "missing-evidence.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="positive cases must include"):
        load_dataset(path)


def test_dataset_rejects_no_result_case_with_evidence(tmp_path: Path):
    row = json.loads(DATASET_PATH.read_text(encoding="utf-8").splitlines()[5])
    row["expected_chunk_contains"] = ["not allowed"]
    path = tmp_path / "unexpected-evidence.jsonl"
    path.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="no-result cases"):
        load_dataset(path)


def test_seed_fixture_reindexes_ready_duplicate_to_refresh_phase3_artifacts(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "leave_policy.md"
    fixture.write_text("fixture", encoding="utf-8")
    ready = _document()
    calls: list[str] = []
    monkeypatch.setattr(
        seed_script.document_service,
        "register_uploaded_document",
        lambda **kwargs: seed_script.document_service.DocumentUploadResult(
            document=ready, duplicate=True
        ),
    )
    monkeypatch.setattr(
        seed_script,
        "run_document_reindex",
        lambda *args, **kwargs: calls.append("reindex"),
    )
    monkeypatch.setattr(
        seed_script,
        "wait_until_ready",
        lambda *args, **kwargs: calls.append("wait") or ready,
    )

    result = seed_script.seed_fixture(
        "Leave Policy",
        fixture,
        settings=seed_script.Settings(),
        timeout_seconds=1,
        poll_interval_seconds=0,
    )

    assert result is ready
    assert calls == ["reindex", "wait"]


def test_seed_fixture_uses_upload_index_services_and_waits(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "leave_policy.md"
    fixture.write_text("fixture", encoding="utf-8")
    uploaded = _document("uploaded")
    ready = _document()
    calls: list[str] = []

    def register(**kwargs):
        calls.append("upload")
        assert kwargs["title"] == "Leave Policy"
        return seed_script.document_service.DocumentUploadResult(document=uploaded)

    monkeypatch.setattr(seed_script.document_service, "register_uploaded_document", register)
    monkeypatch.setattr(
        seed_script,
        "run_document_index",
        lambda *args, **kwargs: calls.append("index"),
    )
    monkeypatch.setattr(
        seed_script,
        "wait_until_ready",
        lambda *args, **kwargs: calls.append("wait") or ready,
    )

    result = seed_script.seed_fixture(
        "Leave Policy",
        fixture,
        settings=seed_script.Settings(),
        timeout_seconds=1,
        poll_interval_seconds=0,
    )

    assert result is ready
    assert calls == ["upload", "index", "wait"]


def test_live_configuration_error_names_fields_without_values():
    settings = seed_script.Settings(
        SUPABASE_URL="https://your-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key",
        QDRANT_URL="https://your-cluster-url.cloud.qdrant.io",
        QDRANT_API_KEY="your-qdrant-key",
        SHOPAIKEY_API_KEY="your-key",
        JINA_API_KEY="your-jina-key",
    )
    with pytest.raises(seed_script.SeedConfigurationError) as exc_info:
        seed_script.require_live_configuration(settings)

    message = str(exc_info.value)
    assert "SUPABASE_SERVICE_ROLE_KEY" in message
    assert "QDRANT_API_KEY" in message
    assert "SHOPAIKEY_API_KEY" in message
    assert "JINA_API_KEY" in message
    assert "your-supabase-service-role-key" not in message


def _chunk(chunk_id: str, content: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "document_id": str(DOCUMENT_ID),
        "file_name": "leave_policy.md",
        "chunk_index": 0,
        "content": content,
    }


def test_retrieval_metrics_match_hand_calculations_and_use_actual_fewer_than_k():
    expected = ["alpha", "bravo", "charlie"]
    before = [
        _chunk("c1", "alpha evidence"),
        _chunk("c2", "irrelevant"),
        _chunk("c3", "bravo evidence"),
    ]
    after = [
        _chunk("c3", "bravo evidence"),
        _chunk("c4", "charlie evidence"),
        _chunk("c2", "irrelevant"),
    ]

    assert recall_at_k(before, expected, k=5) == pytest.approx(2 / 3)
    assert precision_at_k(before, expected, k=5) == pytest.approx(2 / 3)
    assert rerank_lift(before, after, expected, final_k=2) == pytest.approx(1 / 3)


def test_recall_does_not_count_duplicate_results_for_one_expected_chunk_twice():
    duplicated = [
        _chunk("c1", "alpha evidence"),
        _chunk("c2", "overlap repeats alpha evidence"),
    ]

    assert recall_at_k(duplicated, ["alpha"], k=5) == 1.0
    assert precision_at_k(duplicated, ["alpha"], k=5) == 0.5


def test_metric_rates_match_hand_calculated_case_fixtures():
    outcomes = [
        {
            "expected_no_result": False,
            "pre_rerank": [_chunk("c1", "alpha")],
            "post_rerank": [_chunk("c1", "alpha")],
            "context": [_chunk("c1", "alpha")],
            "answer": "Alpha and beta [S1]",
            "sources": [{"chunk_id": "c1"}],
            "citation_validation": {"valid": True, "cited_chunk_ids": ["c1"]},
            "grounding_passed": True,
            "required_answer_terms": ["alpha", "beta"],
            "forbidden_answer_terms": ["gamma"],
            "expected_chunk_contains": ["alpha"],
        },
        {
            "expected_no_result": False,
            "pre_rerank": [],
            "post_rerank": [],
            "context": [],
            "answer": "Gamma",
            "sources": [{"chunk_id": "outside"}],
            "citation_validation": {"valid": False, "cited_chunk_ids": []},
            "grounding_passed": False,
            "required_answer_terms": ["delta", "epsilon"],
            "forbidden_answer_terms": ["gamma"],
            "expected_chunk_contains": ["delta"],
        },
        {
            "expected_no_result": True,
            "pre_rerank": [],
            "post_rerank": [],
            "context": [],
            "answer": "No relevant information found in indexed documents.",
            "sources": [],
            "citation_validation": {"valid": True, "cited_chunk_ids": []},
            "grounding_passed": True,
            "required_answer_terms": [],
            "forbidden_answer_terms": [],
            "expected_chunk_contains": [],
        },
    ]

    assert no_result_rate(outcomes) == pytest.approx(2 / 3)
    assert unexpected_no_result_rate(outcomes) == pytest.approx(1 / 2)
    assert citation_validity_rate(outcomes) == pytest.approx(2 / 3)
    assert grounding_pass_rate(outcomes) == pytest.approx(2 / 3)
    assert answer_term_coverage(outcomes) == pytest.approx(2 / 4)
    assert forbidden_term_rate(outcomes) == pytest.approx(1 / 2)


def test_empty_metric_inputs_and_absent_term_denominators_are_safe():
    assert recall_at_k([], [], k=5) == 0.0
    assert precision_at_k([], ["expected"], k=5) == 0.0
    assert rerank_lift([], [], [], final_k=5) == 0.0
    assert calculate_metrics([], k=5) == {
        "recall_at_5": 0.0,
        "precision_at_5": 0.0,
        "rerank_lift": 0.0,
        "no_result_rate": 0.0,
        "unexpected_no_result_rate": 0.0,
        "citation_validity_rate": 0.0,
        "grounding_pass_rate": 0.0,
        "answer_term_coverage": 0.0,
        "forbidden_term_rate": 0.0,
    }


def test_citation_rate_requires_runtime_validity_and_context_membership():
    outcomes = [
        {
            "answer": "answer",
            "context": [_chunk("c1", "evidence")],
            "citation_validation": {"valid": True, "cited_chunk_ids": ["c1"]},
        },
        {
            "answer": "answer",
            "context": [_chunk("c1", "evidence")],
            "citation_validation": {"valid": True, "cited_chunk_ids": ["outside"]},
        },
        {
            "answer": "answer",
            "context": [_chunk("c1", "evidence")],
            "citation_validation": {"valid": False, "cited_chunk_ids": ["c1"]},
        },
        {"answer": "", "context": [], "citation_validation": {"valid": True}},
    ]

    assert citation_validity_rate(outcomes) == pytest.approx(1 / 3)


def test_threshold_evaluation_uses_exact_default_gates():
    passing = {
        "recall_at_5": 0.80,
        "citation_validity_rate": 1.0,
        "grounding_pass_rate": 0.90,
        "unexpected_no_result_rate": 0.10,
        "forbidden_term_rate": 0.0,
    }
    assert DEFAULT_THRESHOLDS == {
        "min_recall": 0.80,
        "min_citation_validity": 1.0,
        "min_grounding_pass": 0.90,
        "max_unexpected_no_result": 0.10,
        "max_forbidden_term_rate": 0.0,
    }
    assert evaluate_thresholds(passing, k=5) == []

    failing = {**passing, "grounding_pass_rate": 0.89, "forbidden_term_rate": 0.01}
    failures = evaluate_thresholds(failing, k=5)
    assert {failure["metric"] for failure in failures} == {
        "grounding_pass_rate",
        "forbidden_term_rate",
    }


def test_runner_invokes_production_query_graph_and_captures_auditable_fields(tmp_path: Path):
    case = load_dataset(DATASET_PATH)[0]
    invoked: list[dict[str, object]] = []

    class FakeGraph:
        def invoke(self, payload):
            invoked.append(payload)
            relevant = _chunk("c1", case.expected_chunk_contains[0])
            return {
                "retrieved_chunks": [relevant, _chunk("c2", "noise")],
                "reranked_chunks": [relevant],
                "context_chunks": [relevant],
                "answer": "Six days [S1]",
                "sources": [{"chunk_id": "c1"}],
                "citation_validation_result": {
                    "valid": True,
                    "cited_chunk_ids": ["c1"],
                },
                "grounding_result": {"grounded": True, "score": 0.99},
                "answer_verified": True,
                "route": "hybrid",
            }

    report = run_evaluation(
        [case],
        document_ids_by_title={"Leave Policy": str(DOCUMENT_ID)},
        graph=FakeGraph(),
        k=5,
        clock=iter([10.0, 10.125]).__next__,
    )

    assert invoked == [
        {
            "question": case.question,
            "document_ids": [str(DOCUMENT_ID)],
            "save_message": False,
            "filters": case.filters.model_dump(mode="json", exclude_none=True),
        }
    ]
    result = report["cases"][0]
    assert set(result) >= {
        "pre_rerank",
        "post_rerank",
        "context",
        "answer",
        "sources",
        "citation_validation",
        "grounding",
        "grounding_passed",
        "route",
        "latency_ms",
    }
    assert result["latency_ms"] == pytest.approx(125.0)
    assert report["metrics"]["recall_at_5"] == 1.0

    output = write_report(report, output=tmp_path)
    assert output.parent == tmp_path
    assert output.name.startswith("rag-evaluation-")
    assert json.loads(output.read_text(encoding="utf-8"))["metrics"] == report["metrics"]


def test_cli_help_requires_no_live_network_and_documents_all_options():
    result = subprocess.run(
        [sys.executable, "scripts/run_rag_evaluation.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    for option in (
        "--dataset",
        "--output",
        "--k",
        "--min-recall",
        "--min-citation-validity",
        "--min-grounding-pass",
        "--max-unexpected-no-result",
        "--max-forbidden-term-rate",
    ):
        assert option in result.stdout


def test_cli_returns_nonzero_when_any_threshold_fails(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(evaluation_script, "load_dataset", lambda path: [])
    monkeypatch.setattr(evaluation_script, "resolve_document_ids", lambda cases: {})
    monkeypatch.setattr(
        evaluation_script,
        "run_evaluation",
        lambda *args, **kwargs: {
            "metrics": {
                "recall_at_5": 0.79,
                "citation_validity_rate": 1.0,
                "grounding_pass_rate": 0.9,
                "unexpected_no_result_rate": 0.1,
                "forbidden_term_rate": 0.0,
            },
            "cases": [],
        },
    )

    assert evaluation_script.main(["--output", str(tmp_path)]) == 1
