import { useId } from "react";

import type {
  AgentRunEvidence,
  RejectedEvidenceChunk,
  VerifiedEvidenceChunk,
} from "../types/chat";

export type EvidencePanelProps = {
  evidence: AgentRunEvidence;
};

function getVerifiedChunkKey(
  chunk: VerifiedEvidenceChunk,
  index: number,
): string {
  return chunk.chunk_id ?? `${chunk.file_name}-${index}`;
}

function getRejectedChunkKey(
  chunk: RejectedEvidenceChunk,
  index: number,
): string {
  return chunk.chunk_id ?? `${chunk.file_name}-${index}`;
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  const generatedId = useId();
  const verifiedTitleId = `verified-evidence-title-${generatedId}`;
  const rejectedTitleId = `rejected-evidence-title-${generatedId}`;

  return (
    <section className="evidence-panel" aria-label="Answer evidence">
      <section
        className="evidence-panel__group evidence-panel__group--verified"
        aria-labelledby={verifiedTitleId}
      >
        <header className="evidence-panel__group-header">
          <h2 id={verifiedTitleId}>Verified evidence</h2>
          <span className="evidence-panel__count">
            {evidence.verified_chunks.length}
          </span>
        </header>

        {evidence.verified_chunks.length === 0 ? (
          <p className="evidence-panel__empty">
            No verified evidence was returned.
          </p>
        ) : (
          <ul className="evidence-panel__list">
            {evidence.verified_chunks.map((chunk, index) => (
              <li
                className="evidence-panel__item"
                key={getVerifiedChunkKey(chunk, index)}
              >
                <p className="evidence-panel__file">{chunk.file_name}</p>
                <blockquote className="evidence-panel__quote">
                  {chunk.quote}
                </blockquote>
                <dl className="evidence-panel__details">
                  {chunk.page_number != null ? (
                    <div className="evidence-panel__detail">
                      <dt>Page</dt>
                      <dd>{chunk.page_number}</dd>
                    </div>
                  ) : null}
                  {chunk.verification_reason ? (
                    <div className="evidence-panel__detail">
                      <dt>Verification reason</dt>
                      <dd>{chunk.verification_reason}</dd>
                    </div>
                  ) : null}
                  {chunk.supports_simple_reasoning !== undefined ? (
                    <div className="evidence-panel__detail">
                      <dt>Supports simple reasoning</dt>
                      <dd>
                        {chunk.supports_simple_reasoning ? "Yes" : "No"}
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section
        className="evidence-panel__group evidence-panel__group--rejected"
        aria-labelledby={rejectedTitleId}
      >
        <header className="evidence-panel__group-header">
          <h2 id={rejectedTitleId}>Rejected evidence</h2>
          <span className="evidence-panel__count">
            {evidence.rejected_chunks.length}
          </span>
        </header>

        {evidence.rejected_chunks.length === 0 ? (
          <p className="evidence-panel__empty">
            No rejected evidence was returned.
          </p>
        ) : (
          <ul className="evidence-panel__list">
            {evidence.rejected_chunks.map((chunk, index) => (
              <li
                className="evidence-panel__item"
                key={getRejectedChunkKey(chunk, index)}
              >
                <p className="evidence-panel__file">{chunk.file_name}</p>
                <blockquote className="evidence-panel__quote">
                  {chunk.quote}
                </blockquote>
                <dl className="evidence-panel__details">
                  <div className="evidence-panel__detail">
                    <dt>Rejection reason</dt>
                    <dd>{chunk.rejection_reason}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
