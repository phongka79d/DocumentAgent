import React, { useState } from "react";

interface DocumentViewerModalProps {
  documentId: string;
  fileName: string;
  onClose: () => void;
  apiBaseUrl: string;
}

export default function DocumentViewerModal({
  documentId,
  fileName,
  onClose,
  apiBaseUrl,
}: DocumentViewerModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const fileUrl = `${apiBaseUrl}/api/documents/${documentId}/file`;

  // Close modal when pressing Escape key
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="doc-viewer-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Previewing ${fileName}`}
    >
      <div className="doc-viewer-container" onClick={(e) => e.stopPropagation()}>
        <header className="doc-viewer-header">
          <div className="doc-viewer-title-group">
            <span className="material-symbols-outlined doc-viewer-type-icon">
              {fileName.toLowerCase().endsWith(".pdf") ? "picture_as_pdf" : "description"}
            </span>
            <h2 className="doc-viewer-title" title={fileName}>
              {fileName}
            </h2>
          </div>
          <div className="doc-viewer-actions">
            <a
              className="doc-viewer-btn btn-download"
              href={fileUrl}
              download={fileName}
              title="Download file"
            >
              <span className="material-symbols-outlined">download</span>
              <span>Download</span>
            </a>
            <button
              className="doc-viewer-btn btn-close"
              onClick={onClose}
              title="Close preview"
              aria-label="Close document viewer"
              type="button"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </header>

        <div className="doc-viewer-body">
          {isLoading && (
            <div className="doc-viewer-loader">
              <span className="spinner" aria-hidden="true" />
              <p>Loading document view...</p>
            </div>
          )}
          <iframe
            className={`doc-viewer-iframe ${isLoading ? "hidden" : ""}`}
            src={fileUrl}
            title={fileName}
            onLoad={() => setIsLoading(false)}
          />
        </div>
      </div>
    </div>
  );
}
