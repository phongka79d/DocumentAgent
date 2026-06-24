import type { DocumentChunk, SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  formatChunkLabel,
  formatPageRange,
  formatSectionPath,
  getSourceTitle,
} from "../utils/citations";
import ChunkViewerPanel from "./ChunkViewerPanel";
import RetrievalMetrics from "./RetrievalMetrics";

interface ReferencesDrawerProps {
  sources: SourceCitation[];
  selectedSource: SourceCitation | null;
  selectedChunk: DocumentChunk | null;
  isLoading: boolean;
  error: string | null;
  hasPreviousChunk: boolean;
  hasNextChunk: boolean;
  onSelectSource: (source: SourceCitation) => void;
  onClose: () => void;
  onViewPreviousChunk: () => void;
  onViewNextChunk: () => void;
}

export default function ReferencesDrawer({
  sources,
  selectedSource,
  selectedChunk,
  isLoading,
  error,
  hasPreviousChunk,
  hasNextChunk,
  onSelectSource,
  onClose,
  onViewPreviousChunk,
  onViewNextChunk,
}: ReferencesDrawerProps) {
  const isOpen = selectedSource !== null;
  const entries = buildCitationEntries(sources);

  return (
    <aside className={`app-preview-panel references-drawer ${isOpen ? "open" : ""}`}>
      <div className="preview-panel-header">
        <div className="preview-panel-header-title">
          <span className="material-symbols-outlined">fact_check</span>
          <h2>{selectedSource?.file_name ?? "References"}</h2>
        </div>
        <button
          className="preview-close-button"
          onClick={onClose}
          aria-label="Close references drawer"
          type="button"
        >
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      <div className="references-drawer-content">
        <div className="references-navigator" aria-label="Retrieved sources">
          <div className="references-navigator-header">
            <span>Retrieved Sources</span>
            <span>{entries.length}</span>
          </div>

          {entries.length === 0 ? (
            <div className="references-empty">No retrieved chunks for this answer.</div>
          ) : (
            <div className="references-source-stack">
              {entries.map(({ source, label, sourceKey }) => {
                const isSelected =
                  selectedSource?.chunk_id === source.chunk_id &&
                  selectedSource?.document_id === source.document_id;
                const sectionPath = formatSectionPath(source.section_path);

                return (
                  <button
                    key={sourceKey}
                    className={`references-source-button ${isSelected ? "selected" : ""}`}
                    type="button"
                    onClick={() => onSelectSource(source)}
                    aria-label={`Open citation ${label} from ${getSourceTitle(source)}`}
                  >
                    <span className="references-source-topline">
                      <span className="references-source-label">[{label}]</span>
                      <span>{formatPageRange(source.page_start, source.page_end)}</span>
                    </span>
                    <span className="references-source-title" title={source.file_name}>
                      {source.file_name}
                    </span>
                    <span className="references-source-meta" title={sectionPath}>
                      {sectionPath} - {formatChunkLabel(source)}
                    </span>
                    <RetrievalMetrics source={source} compact />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="references-active-panel">
          <ChunkViewerPanel
            selectedSource={selectedSource}
            selectedChunk={selectedChunk}
            isLoading={isLoading}
            error={error}
            hasPreviousChunk={hasPreviousChunk}
            hasNextChunk={hasNextChunk}
            onViewPreviousChunk={onViewPreviousChunk}
            onViewNextChunk={onViewNextChunk}
          />
        </div>
      </div>
    </aside>
  );
}
