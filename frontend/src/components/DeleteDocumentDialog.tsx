import type { DocumentListItem } from "../types/documents";

type DeleteDocumentDialogProps = {
  document: DocumentListItem;
  isDeleting: boolean;
  errorMessage: string | null;
  onConfirm: () => Promise<void>;
  onClose: () => void;
};

export function DeleteDocumentDialog({
  document,
  isDeleting,
  errorMessage,
  onConfirm,
  onClose,
}: DeleteDocumentDialogProps) {
  const titleId = `delete-document-${document.id}-title`;
  const descriptionId = `delete-document-${document.id}-description`;

  function handleBackdropClick(event: React.PointerEvent<HTMLDivElement>) {
    if (isDeleting) {
      event.preventDefault();
      return;
    }

    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  function handleConfirm() {
    void onConfirm().catch(() => undefined);
  }

  return (
    <div
      className="delete-document-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      aria-busy={isDeleting}
      onPointerDown={handleBackdropClick}
    >
      <div className="delete-document-dialog__panel">
        <header className="delete-document-dialog__header">
          <p className="delete-document-dialog__eyebrow">Permanent deletion</p>
          <h2 id={titleId}>Delete this document?</h2>
        </header>

        <div className="delete-document-dialog__body" id={descriptionId}>
          <p>
            This will permanently delete{" "}
            <strong title={document.file_name}>{document.file_name}</strong>.
          </p>
          <div className="delete-document-dialog__warning" role="alert">
            <p className="delete-document-dialog__warning-title">
              The backend will remove all related data, not just hide the file:
            </p>
            <ul>
              <li>Qdrant vectors for this document.</li>
              <li>Stored chunks, entities, and relationship graph data.</li>
              <li>Affected agent runs and their agent steps.</li>
              <li>Related chat messages.</li>
              <li>Chat sessions that become empty after deletion.</li>
            </ul>
          </div>
        </div>

        {errorMessage ? (
          <p className="delete-document-dialog__error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <div className="delete-document-dialog__actions">
          <button
            className="delete-document-dialog__cancel"
            type="button"
            disabled={isDeleting}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="delete-document-dialog__delete"
            type="button"
            disabled={isDeleting}
            onClick={handleConfirm}
          >
            {isDeleting ? "Deleting..." : "Delete permanently"}
          </button>
        </div>
      </div>
    </div>
  );
}
