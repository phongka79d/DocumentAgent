from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.dataset import EvaluationDatasetError, load_dataset
from app.evaluation.metrics import DEFAULT_THRESHOLDS, evaluate_thresholds
from app.evaluation.runner import (
    DEFAULT_RESULTS_DIRECTORY,
    EvaluationRunnerError,
    resolve_document_ids,
    run_evaluation,
    write_report,
)


DEFAULT_DATASET = Path("evaluation/datasets/phase3_v1.jsonl")


def _rate(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("rate must be between 0 and 1")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the production RAG query workflow against an evaluation dataset."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="JSONL dataset path")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESULTS_DIRECTORY,
        help="JSON report file or output directory for a timestamped report",
    )
    parser.add_argument("--k", type=_positive_int, default=5, help="Retrieval metric cutoff (default: 5)")
    parser.add_argument("--min-recall", type=_rate, default=DEFAULT_THRESHOLDS["min_recall"], help="Minimum recall-at-k gate (default: 0.80)")
    parser.add_argument("--min-citation-validity", type=_rate, default=DEFAULT_THRESHOLDS["min_citation_validity"], help="Minimum citation validity rate (default: 1.00)")
    parser.add_argument("--min-grounding-pass", type=_rate, default=DEFAULT_THRESHOLDS["min_grounding_pass"], help="Minimum grounding pass rate (default: 0.90)")
    parser.add_argument("--max-unexpected-no-result", type=_rate, default=DEFAULT_THRESHOLDS["max_unexpected_no_result"], help="Maximum unexpected no-result rate (default: 0.10)")
    parser.add_argument("--max-forbidden-term-rate", type=_rate, default=DEFAULT_THRESHOLDS["max_forbidden_term_rate"], help="Maximum forbidden-term rate (default: 0.00)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_dataset(args.dataset)
        document_ids = resolve_document_ids(cases)
        report = run_evaluation(
            cases,
            document_ids_by_title=document_ids,
            k=args.k,
        )
    except (EvaluationDatasetError, EvaluationRunnerError) as exc:
        print(f"Evaluation could not start: {exc}")
        return 2
    except Exception:
        print("Evaluation failed; inspect provider logs securely.")
        return 2

    failures = evaluate_thresholds(
        report["metrics"],
        k=args.k,
        min_recall=args.min_recall,
        min_citation_validity=args.min_citation_validity,
        min_grounding_pass=args.min_grounding_pass,
        max_unexpected_no_result=args.max_unexpected_no_result,
        max_forbidden_term_rate=args.max_forbidden_term_rate,
    )
    report["thresholds"] = {
        "min_recall": args.min_recall,
        "min_citation_validity": args.min_citation_validity,
        "min_grounding_pass": args.min_grounding_pass,
        "max_unexpected_no_result": args.max_unexpected_no_result,
        "max_forbidden_term_rate": args.max_forbidden_term_rate,
    }
    report["threshold_failures"] = failures
    report_path = write_report(report, output=args.output)
    print(f"Evaluation report: {report_path}")
    for failure in failures:
        print(
            f"FAILED {failure['metric']}: {failure['actual']:.6f} "
            f"{failure['operator']} {failure['threshold']:.6f}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
