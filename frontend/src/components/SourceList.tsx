import type { SourceCitation } from "../api/types";

interface SourceListProps {
  sources: SourceCitation[];
}

function formatSourceCitation(source: SourceCitation, index: number): string {
  const sourceLabel = `Source ${index + 1}: ${source.file_name}, chunk ${source.chunk_index}`;

  if (source.page_start !== null && source.page_end !== null) {
    return `${sourceLabel}, pages ${source.page_start}-${source.page_end}`;
  }

  return sourceLabel;
}

export default function SourceList({ sources }: SourceListProps) {
  if (sources.length === 0) {
    return <div className="source-list__empty">No sources returned</div>;
  }

  return (
    <ol className="source-list">
      {sources.map((source, index) => (
        <li key={source.chunk_id} className="source-list__item">
          <span className="source-list__text">
            {formatSourceCitation(source, index)}
          </span>
        </li>
      ))}
    </ol>
  );
}
