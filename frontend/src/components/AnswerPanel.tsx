import { useId } from "react";

import type { ChatCitation } from "../types/chat";

export type AnswerPanelProps = {
  answer: string;
  confidence: number | null;
  citations: ChatCitation[];
};

function formatConfidence(confidence: number | null): string {
  if (confidence === null) {
    return "Not available";
  }

  return `${Math.round(confidence * 100)}%`;
}

export function AnswerPanel({
  answer,
  confidence,
  citations,
}: AnswerPanelProps) {
  const generatedId = useId();
  const titleId = `answer-panel-title-${generatedId}`;
  const citationsTitleId = `answer-panel-citations-title-${generatedId}`;

  return (
    <article className="answer-panel" aria-labelledby={titleId}>
      <header className="answer-panel__header">
        <h2 id={titleId}>Answer</h2>
        <p className="answer-panel__confidence">
          <span className="answer-panel__confidence-label">Confidence:</span>{" "}
          {formatConfidence(confidence)}
        </p>
      </header>

      <p className="answer-panel__text">{answer}</p>

      <section
        className="answer-panel__citations"
        aria-labelledby={citationsTitleId}
      >
        <h3 id={citationsTitleId}>Citations</h3>
        {citations.length === 0 ? (
          <p className="answer-panel__empty-citations">
            No citations were returned for this answer.
          </p>
        ) : (
          <ul className="answer-panel__citation-list">
            {citations.map((citation, index) => (
              <li
                className="answer-panel__citation"
                key={`${citation.file_name}-${index}`}
              >
                <p className="answer-panel__citation-file">
                  {citation.file_name}
                </p>
                <blockquote className="answer-panel__citation-quote">
                  {citation.quote}
                </blockquote>
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
