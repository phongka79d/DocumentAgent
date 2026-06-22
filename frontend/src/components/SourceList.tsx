import type { SourceCitation } from "../api/types";

interface SourceListProps {
  sources: SourceCitation[];
  selectedSourceChunkId: string | null;
  onSelectSource: (source: SourceCitation) => void;
}

export default function SourceList({
  sources,
  selectedSourceChunkId,
  onSelectSource,
}: SourceListProps) {
  if (sources.length === 0) {
    return <div className="chat-sources-empty">No sources cited for this response.</div>;
  }

  function getFileIcon(fileName: string) {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (ext === "pdf") {
      return <span className="material-symbols-outlined citation-card-icon">picture_as_pdf</span>;
    } else if (ext === "docx" || ext === "doc") {
      return <span className="material-symbols-outlined citation-card-icon docx">description</span>;
    } else if (ext === "txt") {
      return <span className="material-symbols-outlined citation-card-icon txt">article</span>;
    } else if (ext === "md" || ext === "markdown") {
      return <span className="material-symbols-outlined citation-card-icon md">description</span>;
    }
    return <span className="material-symbols-outlined citation-card-icon">insert_drive_file</span>;
  }

  return (
    <div className="chat-sources-list" role="list">
      {sources.map((source) => {
        const isSelected = source.chunk_id === selectedSourceChunkId;
        const pageInfo = source.page_start !== null
          ? `Page ${source.page_start}${source.page_end && source.page_end !== source.page_start ? `-${source.page_end}` : ""}`
          : `Chunk ${source.chunk_index}`;
        const metadataParts: string[] = [];
        if (source.fusion_score !== null && source.fusion_score !== undefined) {
          metadataParts.push(`Fusion: ${(source.fusion_score * 100).toFixed(0)}%`);
        }
        if (source.retrieval_paths && source.retrieval_paths.length > 0) {
          metadataParts.push(`Paths: ${source.retrieval_paths.join(", ")}`);
        }
        if (source.citation_key) {
          metadataParts.push(`Citation: ${source.citation_key}`);
        }
        const scoreText =
          source.rerank_score !== null
            ? `Score: ${(source.rerank_score * 100).toFixed(0)}%`
            : source.qdrant_score !== null
              ? `Score: ${(source.qdrant_score * 100).toFixed(0)}%`
              : "";

        return (
          <button
            key={source.chunk_id}
            className={`citation-card ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectSource(source)}
            aria-label={`View citation from ${source.file_name}, ${pageInfo}`}
          >
            {getFileIcon(source.file_name)}
            <div className="citation-card-details">
              <div className="citation-card-name" title={source.file_name}>
                {source.file_name}
              </div>
              <div className="citation-card-meta">
                {pageInfo}
                {scoreText ? ` | ${scoreText}` : ""}
              </div>
              {metadataParts.length > 0 && (
                <div className="citation-card-meta">
                  {metadataParts.join(" | ")}
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
