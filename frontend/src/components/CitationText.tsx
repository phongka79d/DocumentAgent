import type { SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  findCitationEntryByLabel,
  formatPageRange,
  formatSectionPath,
  getSourceKey,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";

interface CitationTextProps {
  answer: string;
  sources: SourceCitation[];
  selectedSourceChunkId: string | null;
  onSelectSource: (source: SourceCitation) => void;
}

const CITATION_PATTERN = /\[([^\[\]\s]{1,32})\]/g;

export default function CitationText({
  answer,
  sources,
  selectedSourceChunkId,
  onSelectSource,
}: CitationTextProps) {
  const entries = buildCitationEntries(sources);
  const parts: Array<string | JSX.Element> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = CITATION_PATTERN.exec(answer)) !== null) {
    const [fullMatch, rawLabel] = match;
    const entry = findCitationEntryByLabel(entries, rawLabel);

    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }

    if (!entry) {
      parts.push(fullMatch);
    } else {
      const { source, label } = entry;
      const isSelected = source.chunk_id === selectedSourceChunkId;
      const pageRange = formatPageRange(source.page_start, source.page_end);
      const sectionPath = formatSectionPath(source.section_path);
      const preview =
        source.content_preview?.trim() || "Preview text was not returned for this citation.";

      parts.push(
        <span className="citation-pill-wrap" key={`${getSourceKey(source)}:${match.index}`}>
          <button
            className={`citation-pill ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectSource(source)}
            aria-label={`Open citation ${label} from ${source.file_name}, ${pageRange}`}
          >
            [{label}]
          </button>
          <span className="citation-popover" role="tooltip">
            <span className="citation-popover-title">{source.file_name}</span>
            <span className="citation-popover-meta">
              {pageRange} - Chunk {source.chunk_index}
            </span>
            <span className="citation-popover-meta">{sectionPath}</span>
            <span className="citation-popover-preview">{preview}</span>
            <RetrievalMetrics source={source} compact />
          </span>
        </span>,
      );
    }

    lastIndex = match.index + fullMatch.length;
  }

  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return <span className="citation-text">{parts}</span>;
}
