import type { DocumentResponse } from "../api/types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

type DocumentAction = "index" | "reindex" | "delete";

interface DocumentListProps {
  documents: DocumentResponse[];
  error: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
  isBusy: boolean;
  pendingDocumentId: string | null;
  pendingAction: DocumentAction | null;
  onIndex: (documentId: string) => Promise<void>;
  onReindex: (documentId: string) => Promise<void>;
  onDelete: (documentId: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onOpenDocument?: (documentId: string, fileName: string) => void;
  apiBaseUrl: string;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return DATE_FORMATTER.format(date);
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null) return "N/A";
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatStatusLabel(status: DocumentResponse["status"]): string {
  switch (status) {
    case "uploaded":
      return "Uploaded";
    case "processing":
      return "Processing";
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
  }
}

function isDocumentActionBusy(
  documentId: string,
  action: DocumentAction,
  pendingDocumentId: string | null,
  pendingAction: DocumentAction | null,
  isBusy: boolean,
  isLoading: boolean,
): boolean {
  return (
    isBusy ||
    isLoading ||
    (pendingDocumentId === documentId && pendingAction === action)
  );
}

export default function DocumentList({
  documents,
  error,
  isBusy,
  isLoading,
  onDelete,
  onIndex,
  onReindex,
  pendingAction,
  pendingDocumentId,
  onOpenDocument,
  apiBaseUrl,
}: DocumentListProps) {
  const hasDocuments = documents.length > 0;
  const showEmptyState = !hasDocuments && !error && !isLoading;

  if (error) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon" style={{ color: "var(--danger)" }}>error</span>
        <h3 className="state-title" style={{ color: "var(--danger)" }}>Error Loading Documents</h3>
        <p className="state-message">{error}</p>
      </div>
    );
  }

  if (isLoading && !hasDocuments) {
    return (
      <div className="state-container">
        <span className="spinner state-icon" aria-hidden="true" />
        <h3 className="state-title">Loading Documents</h3>
        <p className="state-message">Fetching documents from the server...</p>
      </div>
    );
  }

  if (showEmptyState) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon">folder_open</span>
        <h3 className="state-title">No Documents Found</h3>
        <p className="state-message">Upload some files from the sidebar to begin indexing.</p>
      </div>
    );
  }

  return (
    <div className="documents-grid">
      {documents.map((document) => {
        const isFailed = document.status === "failed";
        const isProcessing = document.status === "processing";
        const isReady = document.status === "ready";

        const indexBusy = isDocumentActionBusy(
          document.id,
          "index",
          pendingDocumentId,
          pendingAction,
          isBusy,
          isLoading,
        );
        const reindexBusy = isDocumentActionBusy(
          document.id,
          "reindex",
          pendingDocumentId,
          pendingAction,
          isBusy,
          isLoading,
        );
        const deleteBusy = isDocumentActionBusy(
          document.id,
          "delete",
          pendingDocumentId,
          pendingAction,
          isBusy,
          isLoading,
        );

        let cardClass = "document-card";
        if (isFailed) cardClass += " failed";
        if (isProcessing) cardClass += " processing";

        return (
          <article key={document.id} className={cardClass} data-status={document.status}>
            {/* Header: Title + Status Badge */}
            <div className="document-card-header">
              <span className="document-card-title" title={document.file_name}>
                {document.file_name}
              </span>
              <span className={`status-badge ${document.status}`}>
                {formatStatusLabel(document.status)}
              </span>
            </div>

            {/* Stats Grid */}
            <div className="document-card-stats">
              <div className="document-stat-item">
                <span className="document-stat-label">Chunks</span>
                <span className="document-stat-value" title={document.total_chunks.toString()}>
                  {document.total_chunks.toLocaleString()}
                </span>
              </div>
              <div className="document-stat-item">
                <span className="document-stat-label">Size</span>
                <span className="document-stat-value">
                  {formatFileSize(document.file_size)}
                </span>
              </div>
              <div className="document-stat-item">
                <span className="document-stat-label">Created</span>
                <span className="document-stat-value" title={document.created_at ?? "-"}>
                  {formatTimestamp(document.created_at)}
                </span>
              </div>
            </div>

            {/* Failed Error Message */}
            {isFailed && document.error_message && (
              <div className="document-card-error" role="alert">
                {document.error_message.trim()}
              </div>
            )}

            {/* Action Buttons */}
            <div className="document-card-actions">
              <button
                className="document-action-btn"
                type="button"
                onClick={() => onOpenDocument?.(document.id, document.file_name)}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>open_in_new</span>
                <span>Open</span>
              </button>
              {!isReady && !isProcessing && (
                <button
                  className="document-action-btn"
                  type="button"
                  onClick={() => void onIndex(document.id)}
                  disabled={indexBusy}
                  aria-busy={pendingDocumentId === document.id && pendingAction === "index"}
                >
                  {pendingDocumentId === document.id && pendingAction === "index" ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>play_arrow</span>
                  )}
                  <span>Index</span>
                </button>
              )}

              {(isReady || isFailed) && (
                <button
                  className="document-action-btn"
                  type="button"
                  onClick={() => void onReindex(document.id)}
                  disabled={reindexBusy}
                  aria-busy={pendingDocumentId === document.id && pendingAction === "reindex"}
                >
                  {pendingDocumentId === document.id && pendingAction === "reindex" ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>sync</span>
                  )}
                  <span>Re-index</span>
                </button>
              )}

              <button
                className="document-action-btn delete"
                type="button"
                onClick={() => void onDelete(document.id)}
                disabled={deleteBusy}
                aria-busy={pendingDocumentId === document.id && pendingAction === "delete"}
              >
                {pendingDocumentId === document.id && pendingAction === "delete" ? (
                  <span className="spinner" aria-hidden="true" />
                ) : (
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>delete</span>
                )}
                <span>Delete</span>
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

