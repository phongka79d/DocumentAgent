import { useId } from "react";

export type SelfCheckPanelProps = {
  output: unknown;
};

type JsonRecord = Record<string, unknown>;

const UNAVAILABLE_VALUE = "N/A";

const SELF_CHECK_FIELDS = [
  ["uses_only_verified_chunks", "Uses only verified chunks"],
  ["has_citation", "Has citation"],
  ["has_unsupported_claims", "Has unsupported claims"],
  ["is_ready", "Is ready"],
] as const;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOwn(record: JsonRecord, fieldName: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, fieldName);
}

function displayText(value: unknown): string {
  return typeof value === "string" && value.trim() !== ""
    ? value
    : UNAVAILABLE_VALUE;
}

function displayConfidence(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : UNAVAILABLE_VALUE;
}

function displayBoolean(value: unknown): string {
  return typeof value === "boolean" ? String(value) : UNAVAILABLE_VALUE;
}

type CitationListProps = {
  citations: unknown;
};

function CitationList({ citations }: CitationListProps) {
  if (!Array.isArray(citations)) {
    return (
      <p className="self-check-panel__state">
        Citation data is unavailable or malformed.
      </p>
    );
  }

  if (citations.length === 0) {
    return <p className="self-check-panel__state">No citations were returned.</p>;
  }

  return (
    <>
      {citations.some((citation) => !isRecord(citation)) ? (
        <p className="self-check-panel__state">
          Some citations are malformed. Unavailable fields are shown as{" "}
          {UNAVAILABLE_VALUE}.
        </p>
      ) : null}
      <ul className="self-check-panel__citation-list">
        {citations.map((citation, index) => {
          const citationRecord = isRecord(citation) ? citation : {};

          return (
            <li className="self-check-panel__citation" key={index}>
              <p className="self-check-panel__citation-file">
                {displayText(citationRecord.file_name)}
              </p>
              <blockquote className="self-check-panel__citation-quote">
                {displayText(citationRecord.quote)}
              </blockquote>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function SelfCheckPanel({ output }: SelfCheckPanelProps) {
  const generatedId = useId();
  const headingId = `self-check-panel-heading-${generatedId}`;

  if (!isRecord(output)) {
    return (
      <section className="self-check-panel" aria-labelledby={headingId}>
        <h3 id={headingId}>Answer and self-check</h3>
        <p className="self-check-panel__state">
          Answer and self-check data is unavailable or malformed.
        </p>
      </section>
    );
  }

  const hasCurrentSelfCheck = hasOwn(output, "self_check_result");
  const hasCompatibilitySelfCheck = hasOwn(output, "self_check");
  const selfCheckValue = hasCurrentSelfCheck
    ? output.self_check_result
    : output.self_check;
  const selfCheck = isRecord(selfCheckValue) ? selfCheckValue : null;
  const selfCheckSource = hasCurrentSelfCheck
    ? "self_check_result"
    : hasCompatibilitySelfCheck
      ? "self_check"
      : null;
  const malformedSelfCheckFields =
    selfCheck !== null &&
    SELF_CHECK_FIELDS.some(
      ([fieldName]) => typeof selfCheck[fieldName] !== "boolean",
    );
  const draftAnswer = isRecord(output.draft_answer)
    ? output.draft_answer
    : null;
  const citationsCount = Array.isArray(output.citations)
    ? String(output.citations.length)
    : UNAVAILABLE_VALUE;

  return (
    <section className="self-check-panel" aria-labelledby={headingId}>
      <header className="self-check-panel__header">
        <h3 id={headingId}>Answer and self-check</h3>
        <dl className="self-check-panel__summary">
          <div>
            <dt>Confidence</dt>
            <dd>{displayConfidence(output.confidence)}</dd>
          </div>
          <div>
            <dt>Citations</dt>
            <dd>{citationsCount}</dd>
          </div>
        </dl>
      </header>

      <section className="self-check-panel__answer">
        <h4>Final answer</h4>
        <p>{displayText(output.final_answer)}</p>
      </section>

      <section className="self-check-panel__answer">
        <h4>Reasoning summary</h4>
        <p>{displayText(output.reasoning_summary)}</p>
      </section>

      {hasOwn(output, "draft_answer") ? (
        <section className="self-check-panel__draft">
          <h4>Draft answer summary</h4>
          {draftAnswer === null ? (
            <p className="self-check-panel__state">
              Draft answer data is malformed. See the raw output for details.
            </p>
          ) : (
            <dl className="self-check-panel__draft-details">
              <div>
                <dt>Answer</dt>
                <dd>{displayText(draftAnswer.final_answer)}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{displayConfidence(draftAnswer.confidence)}</dd>
              </div>
              <div>
                <dt>Reasoning summary</dt>
                <dd>{displayText(draftAnswer.reasoning_summary)}</dd>
              </div>
              <div>
                <dt>Citations</dt>
                <dd>
                  {Array.isArray(draftAnswer.citations)
                    ? String(draftAnswer.citations.length)
                    : UNAVAILABLE_VALUE}
                </dd>
              </div>
            </dl>
          )}
        </section>
      ) : null}

      <section className="self-check-panel__checks">
        <div className="self-check-panel__section-heading">
          <h4>Self-check</h4>
          {selfCheckSource !== null ? (
            <span className="self-check-panel__source">{selfCheckSource}</span>
          ) : null}
        </div>
        {selfCheck === null ? (
          <p className="self-check-panel__state">
            Self-check data is unavailable or malformed.
          </p>
        ) : (
          <>
            {malformedSelfCheckFields ? (
              <p className="self-check-panel__state">
                Some self-check fields are missing or malformed. See the raw
                output for details.
              </p>
            ) : null}
            <dl className="self-check-panel__check-list">
              {SELF_CHECK_FIELDS.map(([fieldName, label]) => (
                <div key={fieldName}>
                  <dt>{label}</dt>
                  <dd>{displayBoolean(selfCheck[fieldName])}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </section>

      <section className="self-check-panel__citations">
        <h4>Citation details</h4>
        <CitationList citations={output.citations} />
      </section>
    </section>
  );
}
