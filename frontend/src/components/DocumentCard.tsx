import { useState } from "react";

import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import { StatusBadge } from "./StatusBadge";
import type { DocumentListItem } from "../types/documents";

type DocumentCardProps = {
  document: DocumentListItem;
  isDeleting?: boolean;
  deleteError?: string | null;
  onDelete?: (document: DocumentListItem) => Promise<void>;
};

function formatUploadTime(createdAt: string) {
  const parsedDate = new Date(createdAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Unknown upload time";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsedDate);
}

function formatChunkCount(chunkCount: number) {
  return `${chunkCount.toLocaleString()} ${chunkCount === 1 ? "chunk" : "chunks"}`;
}

export function DocumentCard({
  document,
  isDeleting = false,
  deleteError = null,
  onDelete,
}: DocumentCardProps) {
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const uploadTime = formatUploadTime(document.created_at);
  const hasProcessingError = Boolean(document.error_message?.trim());
  const canDelete = onDelete !== undefined;

  async function handleDelete() {
    if (!onDelete) {
      return;
    }

    await onDelete(document);
  }

  return (
    <article className="document-card" aria-labelledby={`document-${document.id}`}>
      <div className="document-card__summary">
        <div className="document-card__identity">
          <h3
            className="document-card__name"
            id={`document-${document.id}`}
            title={document.file_name}
          >
            {document.file_name}
          </h3>
          <dl className="document-card__metadata" aria-label="Document metadata">
            <div className="document-card__metadata-item">
              <dt>Type</dt>
              <dd>{document.file_type}</dd>
            </div>
            <div className="document-card__metadata-item">
              <dt>Uploaded</dt>
              <dd>
                <time dateTime={document.created_at}>{uploadTime}</time>
              </dd>
            </div>
            <div className="document-card__metadata-item">
              <dt>Chunks</dt>
              <dd>{formatChunkCount(document.chunk_count)}</dd>
            </div>
          </dl>
        </div>
        <div className="document-card__actions">
          <StatusBadge status={document.status} />
          {canDelete ? (
            <button
              className="document-card__delete"
              type="button"
              disabled={isDeleting}
              onClick={() => {
                setIsDeleteDialogOpen(true);
              }}
            >
              Delete
            </button>
          ) : null}
        </div>
      </div>

      {hasProcessingError ? (
        <p className="document-card__processing-error">
          <strong>Processing error:</strong> {document.error_message}
        </p>
      ) : null}

      {canDelete && isDeleteDialogOpen ? (
        <DeleteDocumentDialog
          document={document}
          isDeleting={isDeleting}
          errorMessage={deleteError}
          onConfirm={handleDelete}
          onClose={() => {
            if (!isDeleting) {
              setIsDeleteDialogOpen(false);
            }
          }}
        />
      ) : null}
    </article>
  );
}
