import type { DocumentChunk, SourceCitation } from "../api/types";
import {
  formatPageRange,
  formatRawScore,
  formatRetrievalPaths,
  formatSectionPath,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";

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

  const primaryScore =
    selectedSource.rerank_score ?? selectedSource.fusion_score ?? selectedSource.qdrant_score;
  const relevanceStr = formatRawScore(primaryScore);
  const pageRange = formatPageRange(
    selectedChunk.page_start ?? selectedSource.page_start,
    selectedChunk.page_end ?? selectedSource.page_end,
  );
  const heading = selectedChunk.heading ?? selectedSource.heading ?? "No heading";
  const sectionPath = formatSectionPath(
    selectedChunk.section_path?.length ? selectedChunk.section_path : selectedSource.section_path,
  );
  const retrievalPaths = formatRetrievalPaths(selectedSource.retrieval_paths);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: "24px" }}>
      {/* Fragment Card */}
      <div className="preview-fragment-card">
        <div className="preview-fragment-header">
          <span className="preview-fragment-tag">Fragment {selectedChunk.chunk_index}</span>
          <span className="preview-fragment-relevance">Relevance: {relevanceStr}</span>
        </div>
        <RetrievalMetrics source={selectedSource} />
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
              {formatRawScore(selectedSource.qdrant_score)}
            </span>
          </div>

          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Rerank Score</span>
            <span className="preview-metadata-value">
              {formatRawScore(selectedSource.rerank_score)}
            </span>
          </div>

          <div className="preview-metadata-card">
            <span className="preview-metadata-label">Fusion Score</span>
            <span className="preview-metadata-value">
              {formatRawScore(selectedSource.fusion_score)}
            </span>
          </div>

          <div className="preview-metadata-card preview-metadata-card-wide">
            <span className="preview-metadata-label">Retrieval Path</span>
            <span className="preview-metadata-value" title={retrievalPaths}>
              {retrievalPaths}
            </span>
          </div>
        </div>
      </div>


    </div>
  );
}

