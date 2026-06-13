import { useId } from "react";

export type RetrievalScoreTableProps = {
  output: unknown;
};

type JsonRecord = Record<string, unknown>;

const UNAVAILABLE_VALUE = "N/A";

const SCORE_COLUMNS = [
  ["semantic_similarity", "Semantic similarity"],
  ["graph_relevance", "Graph relevance"],
  ["keyword_overlap", "Keyword overlap"],
  ["metadata_match", "Metadata match"],
  ["recency_or_position_score", "Position score"],
  ["final_score", "Final score"],
] as const;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function displayText(value: unknown): string {
  return typeof value === "string" && value.trim() !== ""
    ? value
    : UNAVAILABLE_VALUE;
}

function displayScore(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : UNAVAILABLE_VALUE;
}

export function RetrievalScoreTable({ output }: RetrievalScoreTableProps) {
  const generatedId = useId();
  const headingId = `retrieval-score-table-heading-${generatedId}`;

  if (!isRecord(output) || !Array.isArray(output.candidates)) {
    return (
      <section className="retrieval-score-table" aria-labelledby={headingId}>
        <h3 id={headingId}>Retrieval candidates</h3>
        <p className="retrieval-score-table__state">
          Retrieval candidate data is unavailable.
        </p>
      </section>
    );
  }

  if (output.candidates.length === 0) {
    return (
      <section className="retrieval-score-table" aria-labelledby={headingId}>
        <h3 id={headingId}>Retrieval candidates</h3>
        <p className="retrieval-score-table__state">
          No retrieval candidates were returned.
        </p>
      </section>
    );
  }

  const hasMalformedCandidate = output.candidates.some(
    (candidate) => !isRecord(candidate),
  );

  return (
    <section className="retrieval-score-table" aria-labelledby={headingId}>
      <h3 id={headingId}>Retrieval candidates</h3>
      {hasMalformedCandidate ? (
        <p className="retrieval-score-table__state">
          Some retrieval candidates are malformed. Unavailable fields are shown
          as {UNAVAILABLE_VALUE}.
        </p>
      ) : null}
      <div className="retrieval-score-table__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Chunk ID</th>
              <th scope="col">File name</th>
              {SCORE_COLUMNS.map(([, label]) => (
                <th scope="col" key={label}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {output.candidates.map((candidate, index) => {
              const candidateRecord = isRecord(candidate) ? candidate : {};

              return (
                <tr key={index}>
                  <td>{displayText(candidateRecord.chunk_id)}</td>
                  <td>{displayText(candidateRecord.file_name)}</td>
                  {SCORE_COLUMNS.map(([fieldName]) => (
                    <td key={fieldName}>
                      {displayScore(candidateRecord[fieldName])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
