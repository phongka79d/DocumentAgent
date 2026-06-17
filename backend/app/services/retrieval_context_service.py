from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.schemas.retrieval import HybridRetrievalCandidate
from app.services import hybrid_retrieval_service, supabase_service


ChunkLookup = Callable[[str, list[int]], list[dict[str, Any]]]


def expand_retrieval_context(
    question: str,
    anchors: list[HybridRetrievalCandidate],
    *,
    context_window: int,
    max_context_candidates: int,
    min_parent_score: float = 0.0,
    chunk_lookup: ChunkLookup = supabase_service.list_document_chunks_by_indexes,
) -> list[HybridRetrievalCandidate]:
    if context_window <= 0 or max_context_candidates <= 0 or not anchors:
        return list(anchors)

    existing_ids = {candidate.chunk_id for candidate in anchors}
    requested_indexes: dict[UUID, set[int]] = {}
    parent_by_position: dict[
        tuple[UUID, int],
        HybridRetrievalCandidate,
    ] = {}

    for anchor in anchors:
        if anchor.final_score < min_parent_score:
            continue
        if anchor.chunk_index is None:
            continue
        for offset in range(-context_window, context_window + 1):
            neighbor_index = anchor.chunk_index + offset
            if offset == 0 or neighbor_index < 0:
                continue
            requested_indexes.setdefault(anchor.document_id, set()).add(
                neighbor_index
            )
            parent_by_position.setdefault(
                (anchor.document_id, neighbor_index),
                anchor,
            )

    selected_document_ids = list(
        dict.fromkeys(candidate.document_id for candidate in anchors)
    )
    context_candidates: list[HybridRetrievalCandidate] = []
    for document_id, indexes in requested_indexes.items():
        rows = chunk_lookup(str(document_id), sorted(indexes))
        for row in rows:
            chunk_id = UUID(str(row["id"]))
            chunk_index = int(row["chunk_index"])
            if chunk_id in existing_ids:
                continue
            parent = parent_by_position.get((document_id, chunk_index))
            if parent is None:
                continue

            candidate = HybridRetrievalCandidate(
                chunk_id=chunk_id,
                document_id=document_id,
                file_name=parent.file_name,
                file_type=parent.file_type,
                content=row.get("content"),
                content_preview=None,
                page_number=row.get("page_number"),
                section_title=row.get("section_title"),
                chunk_index=chunk_index,
                semantic_similarity=0.0,
                metadata=None,
                graph_relevance=0.0,
                keyword_overlap=0.0,
                metadata_match=0.0,
                recency_or_position_score=0.0,
                final_score=0.0,
                retrieval_reason=(
                    "Adjacent source context for retrieved chunk "
                    f"index {parent.chunk_index}."
                ),
            )
            context_candidates.append(
                hybrid_retrieval_service.score_hybrid_candidate(
                    candidate,
                    question=question,
                    document_ids=selected_document_ids,
                    preserve_retrieval_reason=True,
                )
            )
            existing_ids.add(chunk_id)
            if len(context_candidates) >= max_context_candidates:
                break
        if len(context_candidates) >= max_context_candidates:
            break

    return sorted(
        [*anchors, *context_candidates],
        key=lambda candidate: candidate.final_score,
        reverse=True,
    )


__all__ = ["ChunkLookup", "expand_retrieval_context"]
