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

  return score.toFixed(3);
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
    return <div className="chunk-viewer-state">No source selected</div>;
  }

  if (isLoading) {
    return <div className="chunk-viewer-state">Loading source</div>;
  }

  if (error) {
    return <div className="chunk-viewer-state chunk-viewer-state--error">Unable to load source</div>;
  }

  if (!selectedChunk) {
    return (
      <div className="chunk-viewer-state chunk-viewer-state--warning">
        Selected chunk not found
      </div>
    );
  }

  const pageRange =
    formatPageRange(selectedChunk.page_start, selectedChunk.page_end) ??
    formatPageRange(selectedSource.page_start, selectedSource.page_end);
  const heading = selectedChunk.heading ?? selectedSource.heading;
  const sectionPath =
    selectedChunk.section_path.length > 0
      ? selectedChunk.section_path.join(" / ")
      : null;

  return (
    <div className="chunk-viewer">
      <div className="chunk-viewer__toolbar">
        <div className="chunk-viewer__identity">
          <div className="chunk-viewer__file" title={selectedSource.file_name}>
            {selectedSource.file_name}
          </div>
          <div className="chunk-viewer__chunk">Chunk {selectedChunk.chunk_index}</div>
        </div>

        <div className="chunk-viewer__nav">
          <button
            className="button button--secondary button--compact chunk-viewer__nav-button"
            type="button"
            onClick={onViewPreviousChunk}
            disabled={!hasPreviousChunk}
          >
            Previous
          </button>
          <button
            className="button button--secondary button--compact chunk-viewer__nav-button"
            type="button"
            onClick={onViewNextChunk}
            disabled={!hasNextChunk}
          >
            Next
          </button>
        </div>
      </div>

      <dl className="chunk-viewer__meta">
        {pageRange ? (
          <div className="chunk-viewer__meta-item">
            <dt>Pages</dt>
            <dd>{pageRange}</dd>
          </div>
        ) : null}

        {heading ? (
          <div className="chunk-viewer__meta-item">
            <dt>Heading</dt>
            <dd>{heading}</dd>
          </div>
        ) : null}

        {sectionPath ? (
          <div className="chunk-viewer__meta-item">
            <dt>Section path</dt>
            <dd>{sectionPath}</dd>
          </div>
        ) : null}

        <div className="chunk-viewer__meta-item">
          <dt>Qdrant score</dt>
          <dd>{formatScore(selectedSource.qdrant_score)}</dd>
        </div>

        <div className="chunk-viewer__meta-item">
          <dt>Rerank score</dt>
          <dd>{formatScore(selectedSource.rerank_score)}</dd>
        </div>
      </dl>

      <div className="chunk-viewer__content">{selectedChunk.content}</div>
    </div>
  );
}
