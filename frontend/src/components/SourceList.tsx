import type { SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  formatChunkLabel,
  formatPageRange,
  formatSectionPath,
  getSourceTitle,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";

interface SourceListProps {
  sources: SourceCitation[];
  selectedSourceChunkId: string | null;
  onSelectSource: (source: SourceCitation) => void;
}

function getFileIcon(fileName: string) {
  const ext = fileName.split(".").pop()?.toLowerCase();
  if (ext === "pdf") {
    return <span className="material-symbols-outlined citation-card-icon">picture_as_pdf</span>;
  }
  if (ext === "docx" || ext === "doc") {
    return <span className="material-symbols-outlined citation-card-icon docx">description</span>;
  }
  if (ext === "txt") {
    return <span className="material-symbols-outlined citation-card-icon txt">article</span>;
  }
  if (ext === "md" || ext === "markdown") {
    return <span className="material-symbols-outlined citation-card-icon md">description</span>;
  }
  return <span className="material-symbols-outlined citation-card-icon">insert_drive_file</span>;
}

export default function SourceList({
  sources,
  selectedSourceChunkId,
  onSelectSource,
}: SourceListProps) {
  if (sources.length === 0) {
    return <div className="chat-sources-empty">No sources cited for this response.</div>;
  }

  const entries = buildCitationEntries(sources);

  return (
    <div className="chat-sources-list" role="list">
      {entries.map(({ source, label, sourceKey }) => {
        const isSelected = source.chunk_id === selectedSourceChunkId;
        const pageInfo = formatPageRange(source.page_start, source.page_end);
        const sectionPath = formatSectionPath(source.section_path);

        return (
          <button
            key={sourceKey}
            className={`citation-card ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectSource(source)}
            aria-label={`View citation ${label} from ${getSourceTitle(source)}`}
          >
            <span className="citation-card-label">[{label}]</span>
            {getFileIcon(source.file_name)}
            <span className="citation-card-details">
              <span className="citation-card-name" title={source.file_name}>
                {source.file_name}
              </span>
              <span className="citation-card-meta">
                {pageInfo} - {formatChunkLabel(source)}
              </span>
              <span className="citation-card-meta" title={sectionPath}>
                {sectionPath}
              </span>
              <RetrievalMetrics source={source} compact />
            </span>
          </button>
        );
      })}
    </div>
  );
}
