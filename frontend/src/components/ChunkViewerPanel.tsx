import type { DocumentChunk, SourceCitation } from "../api/types";

interface ChunkViewerPanelProps {
  selectedSource: SourceCitation | null;
  selectedChunk: DocumentChunk | null;
  isLoading: boolean;
  error: string | null;
  hasPreviousChunk: boolean;
  hasNextChunk: boolean;
  onViewPreviousChunk: () => void;
  onViewNextChunk: () => void;
}

function formatPageRange(
  pageStart: number | null | undefined,
  pageEnd: number | null | undefined,
): string | null {
  if (pageStart === null || pageStart === undefined) {
    return null;
  }

  if (pageEnd === null || pageEnd === undefined || pageEnd === pageStart) {
    return `Page ${pageStart}`;
  }

  return `Pages ${pageStart}-${pageEnd}`;
}

function formatScore(score: number | null): string {
  if (score === null) {
    return "N/A";
  }
  return `${(score * 100).toFixed(0)}%`;
}

export default function ChunkViewerPanel({
  selectedSource,
  selectedChunk,
  isLoading,
  error,
  hasPreviousChunk,
  hasNextChunk,
  onViewPreviousChunk,
  onViewNextChunk,
}: ChunkViewerPanelProps) {
  if (!selectedSource) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon">description</span>
        <h3 className="state-title">No Source Selected</h3>
        <p className="state-message">
          Click on a citation card in the chat panel to view its full text and metadata.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="state-container">
        <span className="spinner state-icon" aria-hidden="true" />
        <h3 className="state-title">Loading Source</h3>
        <p className="state-message">Fetching document fragment from server...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon" style={{ color: "var(--danger)" }}>error</span>
        <h3 className="state-title" style={{ color: "var(--danger)" }}>Error Loading Source</h3>
        <p className="state-message">{error}</p>
      </div>
    );
  }

  if (!selectedChunk) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon" style={{ color: "var(--warning)" }}>warning</span>
        <h3 className="state-title">Chunk Not Found</h3>
        <p className="state-message">The requested document fragment could not be located.</p>
      </div>
    );
  }

  const scoreVal = selectedSource.rerank_score ?? selectedSource.qdrant_score;
  const relevanceStr = formatScore(scoreVal);

  const pageRange =
    formatPageRange(selectedChunk.page_start, selectedChunk.page_end) ??
    formatPageRange(selectedSource.page_start, selectedSource.page_end) ??
    "N/A";
  const heading = selectedChunk.heading ?? selectedSource.heading ?? "N/A";
  const sectionPath =
    selectedChunk.section_path && selectedChunk.section_path.length > 0
      ? selectedChunk.section_path.join(" / ")
      : "N/A";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: "24px" }}>
      {/* Fragment Card */}
      <div className="preview-fragment-card">
        <div className="preview-fragment-header">
          <span className="preview-fragment-tag">Fragment {selectedChunk.chunk_index}</span>
          <span className="preview-fragment-relevance">Relevance: {relevanceStr}</span>
        </div>
        <div className="preview-fragment-text">
          {selectedChunk.content}
        </div>

        {/* Fragment Navigation */}
        <div className="chunk-viewer-nav-group">
          <button
            className="chunk-viewer-nav-btn"
            type="button"
            onClick={onViewPreviousChunk}
            disabled={!hasPreviousChunk}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>navigate_before</span>
            Previous
          </button>
          <button
            className="chunk-viewer-nav-btn"
            type="button"
            onClick={onViewNextChunk}
            disabled={!hasNextChunk}
          >
            Next
            <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>navigate_next</span>
          </button>
        </div>
      </div>

      {/* Metadata Section */}
      <div className="preview-metadata-section">
        <h3 className="preview-metadata-title">Metadata</h3>
        <div className="preview-metadata-grid">
          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Page Range</span>
            <span className="preview-metadata-value" title={pageRange}>{pageRange}</span>
          </div>

          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Heading</span>
            <span className="preview-metadata-value" title={heading}>{heading}</span>
          </div>

          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Section Path</span>
            <span className="preview-metadata-value" title={sectionPath}>{sectionPath}</span>
          </div>

          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Qdrant Score</span>
            <span className="preview-metadata-value">
              {selectedSource.qdrant_score !== null ? selectedSource.qdrant_score.toFixed(4) : "N/A"}
            </span>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="preview-full-doc-container">
        <button 
          className="btn-outline" 
          disabled 
          title="Full document viewer requires premium document integration."
        >
          <span className="material-symbols-outlined">open_in_new</span>
          Open Full Document
        </button>
      </div>
    </div>
  );
}

