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
  isRefreshing,
  onDelete,
  onIndex,
  onRefresh,
  onReindex,
  pendingAction,
  pendingDocumentId,
}: DocumentListProps) {
  const hasDocuments = documents.length > 0;
  const showEmptyState = !hasDocuments && !error && !isLoading;

  return (
    <section className="panel document-list-panel" aria-label="Documents">
      <div className="panel-heading">
        <h2>Documents</h2>

        <button
          className="button button--secondary button--compact"
          type="button"
          onClick={() => void onRefresh()}
          disabled={isBusy || isLoading || isRefreshing}
          aria-busy={isRefreshing}
        >
          {isRefreshing ? (
            <span className="button-spinner" aria-hidden="true" />
          ) : null}
          <span>{isRefreshing ? "Refreshing" : "Refresh"}</span>
        </button>
      </div>

      {error ? (
        <div className="document-list-error" role="alert">
          {error}
        </div>
      ) : null}

      {isLoading && !hasDocuments ? (
        <div className="document-list-state" aria-live="polite">
          Loading documents
        </div>
      ) : hasDocuments ? (
        <div className="document-list">
          {documents.map((document) => {
            const rowBusy = pendingDocumentId === document.id;
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

            return (
              <article
                key={document.id}
                className={`document-row ${
                  document.status === "failed" ? "document-row--failed" : ""
                }`}
                data-status={document.status}
              >
                <div className="document-row__header">
                  <div className="document-row__identity">
                    <span
                      className="document-row__name"
                      title={document.file_name}
                    >
                      {document.file_name}
                    </span>
                    <span
                      className={`status-tag status-tag--${document.status}`}
                    >
                      {formatStatusLabel(document.status)}
                    </span>
                  </div>

                  <div className="document-row__actions">
                    <button
                      className="button button--secondary button--compact"
                      type="button"
                      onClick={() => void onIndex(document.id)}
                      disabled={indexBusy}
                      aria-busy={
                        pendingDocumentId === document.id &&
                        pendingAction === "index"
                      }
                    >
                      {pendingDocumentId === document.id &&
                      pendingAction === "index" ? (
                        <span className="button-spinner" aria-hidden="true" />
                      ) : null}
                      <span>Index</span>
                    </button>

                    <button
                      className="button button--secondary button--compact"
                      type="button"
                      onClick={() => void onReindex(document.id)}
                      disabled={reindexBusy}
                      aria-busy={
                        pendingDocumentId === document.id &&
                        pendingAction === "reindex"
                      }
                    >
                      {pendingDocumentId === document.id &&
                      pendingAction === "reindex" ? (
                        <span className="button-spinner" aria-hidden="true" />
                      ) : null}
                      <span>Re-index</span>
                    </button>

                    <button
                      className="button button--danger button--compact"
                      type="button"
                      onClick={() => void onDelete(document.id)}
                      disabled={deleteBusy}
                      aria-busy={
                        pendingDocumentId === document.id &&
                        pendingAction === "delete"
                      }
                    >
                      {pendingDocumentId === document.id &&
                      pendingAction === "delete" ? (
                        <span className="button-spinner" aria-hidden="true" />
                      ) : null}
                      <span>Delete</span>
                    </button>
                  </div>
                </div>

                <dl className="document-row__meta">
                  <div className="document-metric">
                    <dt>Total chunks</dt>
                    <dd>{document.total_chunks.toLocaleString()}</dd>
                  </div>

                  <div className="document-metric">
                    <dt>Created</dt>
                    <dd title={document.created_at ?? "-"}>
                      {formatTimestamp(document.created_at)}
                    </dd>
                  </div>

                  <div className="document-metric">
                    <dt>Indexed</dt>
                    <dd title={document.indexed_at ?? "-"}>
                      {formatTimestamp(document.indexed_at)}
                    </dd>
                  </div>
                </dl>

                {document.status === "failed" ? (
                  <div className="document-row__error" role="status">
                    {document.error_message?.trim() || "Failed"}
                  </div>
                ) : null}

                {rowBusy ? <span className="sr-only">Action in progress</span> : null}
              </article>
            );
          })}
        </div>
      ) : showEmptyState ? (
        <div className="document-list-state" aria-live="polite">
          No documents
        </div>
      ) : null}
    </section>
  );
}
