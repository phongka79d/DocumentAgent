import { useId } from "react";

export type VerificationResultPanelProps = {
  output: unknown;
};

type JsonRecord = Record<string, unknown>;
type ChunkGroupKind = "verified" | "rejected";

const UNAVAILABLE_VALUE = "N/A";

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function displayText(value: unknown): string {
  return typeof value === "string" && value.trim() !== ""
    ? value
    : UNAVAILABLE_VALUE;
}

function displayPage(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }

  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function displayBoolean(value: unknown): string | null {
  return typeof value === "boolean" ? (value ? "Yes" : "No") : null;
}

function displayConfidence(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : UNAVAILABLE_VALUE;
}

function displayMissingInformation(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return UNAVAILABLE_VALUE;
}

type ChunkGroupProps = {
  chunks: unknown;
  generatedId: string;
  kind: ChunkGroupKind;
};

function ChunkGroup({ chunks, generatedId, kind }: ChunkGroupProps) {
  const isVerified = kind === "verified";
  const title = isVerified ? "Verified chunks" : "Rejected chunks";
  const headingId = `${kind}-verification-chunks-${generatedId}`;
  const reasonField = isVerified
    ? "verification_reason"
    : "rejection_reason";
  const reasonLabel = isVerified
    ? "Verification reason"
    : "Rejection reason";

  return (
    <section
      className={`verification-result-panel__group verification-result-panel__group--${kind}`}
      aria-labelledby={headingId}
    >
      <header className="verification-result-panel__group-header">
        <h4 id={headingId}>{title}</h4>
        <span className="verification-result-panel__count">
          {Array.isArray(chunks) ? chunks.length : UNAVAILABLE_VALUE}
        </span>
      </header>

      {!Array.isArray(chunks) ? (
        <p className="verification-result-panel__state">
          {title} data is unavailable or malformed.
        </p>
      ) : chunks.length === 0 ? (
        <p className="verification-result-panel__state">
          No {kind} chunks were returned.
        </p>
      ) : (
        <>
          {chunks.some((chunk) => !isRecord(chunk)) ? (
            <p className="verification-result-panel__state">
              Some {kind} chunks are malformed. Unavailable fields are shown as{" "}
              {UNAVAILABLE_VALUE}.
            </p>
          ) : null}
          <ul className="verification-result-panel__list">
            {chunks.map((chunk, index) => {
              const chunkRecord = isRecord(chunk) ? chunk : {};
              const page = displayPage(chunkRecord.page_number);
              const simpleReasoning = displayBoolean(
                chunkRecord.supports_simple_reasoning,
              );

              return (
                <li className="verification-result-panel__item" key={index}>
                  <dl className="verification-result-panel__details">
                    <div className="verification-result-panel__detail">
                      <dt>Chunk ID</dt>
                      <dd>{displayText(chunkRecord.chunk_id)}</dd>
                    </div>
                    <div className="verification-result-panel__detail">
                      <dt>Document ID</dt>
                      <dd>{displayText(chunkRecord.document_id)}</dd>
                    </div>
                    <div className="verification-result-panel__detail">
                      <dt>File name</dt>
                      <dd>{displayText(chunkRecord.file_name)}</dd>
                    </div>
                    {page !== null ? (
                      <div className="verification-result-panel__detail">
                        <dt>Page</dt>
                        <dd>{page}</dd>
                      </div>
                    ) : null}
                    <div className="verification-result-panel__detail">
                      <dt>{reasonLabel}</dt>
                      <dd>{displayText(chunkRecord[reasonField])}</dd>
                    </div>
                    {simpleReasoning !== null ? (
                      <div className="verification-result-panel__detail">
                        <dt>Supports simple reasoning</dt>
                        <dd>{simpleReasoning}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <blockquote className="verification-result-panel__quote">
                    {displayText(chunkRecord.quote)}
                  </blockquote>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

export function VerificationResultPanel({
  output,
}: VerificationResultPanelProps) {
  const generatedId = useId();
  const headingId = `verification-result-heading-${generatedId}`;

  if (!isRecord(output)) {
    return (
      <section
        className="verification-result-panel"
        aria-labelledby={headingId}
      >
        <h3 id={headingId}>Verification result</h3>
        <p className="verification-result-panel__state">
          Verification result data is unavailable or malformed.
        </p>
      </section>
    );
  }

  const missingInformation = displayMissingInformation(
    output.missing_information,
  );
  const missingInformationIsMalformed =
    output.missing_information !== undefined &&
    typeof output.missing_information !== "boolean";

  return (
    <section
      className="verification-result-panel"
      aria-labelledby={headingId}
    >
      <header className="verification-result-panel__header">
        <h3 id={headingId}>Verification result</h3>
        <dl className="verification-result-panel__summary">
          <div>
            <dt>Missing information</dt>
            <dd>{missingInformation}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{displayConfidence(output.confidence)}</dd>
          </div>
        </dl>
      </header>

      {missingInformationIsMalformed ? (
        <p className="verification-result-panel__state">
          Missing information has a malformed value. See the raw output for
          details.
        </p>
      ) : null}

      <div className="verification-result-panel__groups">
        <ChunkGroup
          chunks={output.verified_chunks}
          generatedId={generatedId}
          kind="verified"
        />
        <ChunkGroup
          chunks={output.rejected_chunks}
          generatedId={generatedId}
          kind="rejected"
        />
      </div>
    </section>
  );
}
