from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from pydantic import Field, ValidationError, field_validator, model_validator

from app.models.schemas import APIModel, RetrievalFilters


FIXTURE_FILES = {
    "Leave Policy": "leave_policy.md",
    "Pricing Policy": "pricing_policy.md",
    "Security Policy": "security_policy.md",
}
DEFAULT_FIXTURE_DIRECTORY = Path(__file__).resolve().parents[2] / "evaluation" / "fixtures"


class EvaluationDatasetError(ValueError):
    """Raised when an evaluation dataset violates its contract."""


class EvaluationCase(APIModel):
    """One deterministic retrieval and answer-quality expectation."""

    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    document_titles: list[str]
    expected_chunk_contains: list[str]
    required_answer_terms: list[str]
    forbidden_answer_terms: list[str]
    expected_no_result: bool
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    tags: list[str] = Field(min_length=1)

    @field_validator(
        "document_titles",
        "expected_chunk_contains",
        "required_answer_terms",
        "forbidden_answer_terms",
        "tags",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        normalized: list[Any] = []
        for item in value:
            cleaned = item.strip() if isinstance(item, str) else item
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @model_validator(mode="after")
    def validate_expectations(self) -> EvaluationCase:
        if self.expected_no_result:
            if self.expected_chunk_contains:
                raise ValueError("no-result cases must have empty expected evidence")
            if self.required_answer_terms:
                raise ValueError("no-result cases must have no required answer terms")
        else:
            if not self.document_titles:
                raise ValueError("positive cases must reference at least one document title")
            if not self.expected_chunk_contains:
                raise ValueError("positive cases must include expected evidence")
        return self


def _read_fixture_texts(fixture_directory: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for title, file_name in FIXTURE_FILES.items():
        path = fixture_directory / file_name
        if not path.is_file():
            raise EvaluationDatasetError(f"Missing fixture for {title}: {file_name}")
        try:
            texts[title] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise EvaluationDatasetError(f"Fixture is not UTF-8 text: {file_name}") from exc
    return texts


def _validate_fixture_references(
    cases: Iterable[EvaluationCase], fixture_texts: dict[str, str]
) -> None:
    known_titles = set(fixture_texts)
    for case in cases:
        unknown_titles = set(case.document_titles) - known_titles
        if unknown_titles:
            raise EvaluationDatasetError(
                f"Case {case.case_id} references unknown titles: "
                + ", ".join(sorted(unknown_titles))
            )

        for phrase in case.expected_chunk_contains:
            occurrence_counts = {
                title: text.count(phrase) for title, text in fixture_texts.items()
            }
            total_occurrences = sum(occurrence_counts.values())
            if total_occurrences != 1:
                raise EvaluationDatasetError(
                    f"Case {case.case_id} evidence must occur exactly once across fixtures: "
                    f"{phrase!r}"
                )
            matching_title = next(
                title for title, count in occurrence_counts.items() if count == 1
            )
            if matching_title not in case.document_titles:
                raise EvaluationDatasetError(
                    f"Case {case.case_id} evidence is outside its referenced titles: "
                    f"{phrase!r}"
                )


def validate_dataset(
    cases: list[EvaluationCase],
    *,
    fixture_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> list[EvaluationCase]:
    if not cases:
        raise EvaluationDatasetError("Dataset must contain at least one case")

    counts = Counter(case.case_id for case in cases)
    duplicate_ids = sorted(case_id for case_id, count in counts.items() if count > 1)
    if duplicate_ids:
        raise EvaluationDatasetError(
            "Duplicate case IDs: " + ", ".join(duplicate_ids)
        )

    _validate_fixture_references(cases, _read_fixture_texts(fixture_directory))
    return cases


def load_dataset(
    path: str | Path,
    *,
    fixture_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> list[EvaluationCase]:
    dataset_path = Path(path)
    cases: list[EvaluationCase] = []
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise EvaluationDatasetError(f"Unable to read dataset: {dataset_path}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise EvaluationDatasetError(f"Blank JSONL row at line {line_number}")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationDatasetError(
                f"Invalid JSON at line {line_number}"
            ) from exc
        try:
            cases.append(EvaluationCase.model_validate(payload))
        except ValidationError as exc:
            raise EvaluationDatasetError(
                f"Invalid dataset row at line {line_number}: {exc}"
            ) from exc

    return validate_dataset(cases, fixture_directory=fixture_directory)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a RAG evaluation JSONL dataset.")
    parser.add_argument("dataset", type=Path, help="Path to the versioned JSONL dataset")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURE_DIRECTORY,
        help="Directory containing the three evaluation fixtures",
    )
    args = parser.parse_args(argv)
    try:
        cases = load_dataset(args.dataset, fixture_directory=args.fixtures)
    except EvaluationDatasetError as exc:
        parser.exit(1, f"Dataset validation failed: {exc}\n")
    print(f"Dataset validation passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
