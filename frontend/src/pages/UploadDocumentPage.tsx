import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  getDocumentApiError,
  listDocuments,
  uploadDocument,
  type DocumentUploadProgress,
} from "../api/documents";
import { DocumentCard } from "../components/DocumentCard";
import { StatusBadge } from "../components/StatusBadge";
import { UploadBox } from "../components/UploadBox";
import type {
  DocumentListItem,
  DocumentUploadResponse,
} from "../types/documents";
import { validateSelectedFile } from "../utils/fileValidation";

type UploadState = "idle" | "uploading";
type RecentDocumentsState = "loading" | "ready" | "error";
const RECENT_DOCUMENT_LIMIT = 3;

function getUploadStatusMessage(result: DocumentUploadResponse) {
  switch (result.status) {
    case "uploaded":
      return "The backend accepted the file and marked it as uploaded.";
    case "processing":
      return "The backend reports that processing is in progress.";
    case "ready":
      return "The backend reports that this document is ready.";
    case "failed":
      return "The backend reports that this document failed.";
  }
}

export function UploadDocumentPage() {
  const activeUploadRef = useRef(false);
  const activeRecentDocumentsRequestRef = useRef(false);
  const queuedRecentDocumentsRefreshRef = useRef(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(
    null,
  );
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadProgress, setUploadProgress] =
    useState<DocumentUploadProgress | null>(null);
  const [recentDocuments, setRecentDocuments] = useState<DocumentListItem[]>([]);
  const [recentDocumentsError, setRecentDocumentsError] = useState<string | null>(
    null,
  );
  const [recentDocumentsState, setRecentDocumentsState] =
    useState<RecentDocumentsState>("loading");

  const isUploading = uploadState === "uploading";
  const canUpload = selectedFile !== null && validationError === null && !isUploading;
  const hasRecentDocuments = recentDocuments.length > 0;

  async function loadRecentDocuments() {
    if (activeRecentDocumentsRequestRef.current) {
      queuedRecentDocumentsRefreshRef.current = true;
      return;
    }

    do {
      queuedRecentDocumentsRefreshRef.current = false;
      activeRecentDocumentsRequestRef.current = true;
      setRecentDocumentsState("loading");
      setRecentDocumentsError(null);

      try {
        const response = await listDocuments();
        setRecentDocuments(response.documents.slice(0, RECENT_DOCUMENT_LIMIT));
        setRecentDocumentsState("ready");
      } catch (error) {
        setRecentDocuments([]);
        setRecentDocumentsError(getDocumentApiError(error).message);
        setRecentDocumentsState("error");
      } finally {
        activeRecentDocumentsRequestRef.current = false;
      }
    } while (queuedRecentDocumentsRefreshRef.current);
  }

  useEffect(() => {
    void loadRecentDocuments();
  }, []);

  function handleFileSelect(file: File) {
    const validation = validateSelectedFile(file);

    setSelectedFile(validation.isValid ? file : null);
    setValidationError(validation.isValid ? null : validation.message);
    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(null);
  }

  function handleFileReject(message: string) {
    setSelectedFile(null);
    setValidationError(message);
    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (activeUploadRef.current) {
      return;
    }

    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(null);

    if (!selectedFile) {
      setValidationError("Choose a supported document before uploading.");
      return;
    }

    const validation = validateSelectedFile(selectedFile);
    if (!validation.isValid) {
      setValidationError(validation.message);
      setSelectedFile(null);
      return;
    }

    setValidationError(null);
    activeUploadRef.current = true;
    setUploadState("uploading");

    try {
      const uploadedDocument = await uploadDocument(selectedFile, (progress) => {
        setUploadProgress(progress);
      });

      setUploadResult(uploadedDocument);
      await loadRecentDocuments();
    } catch (error) {
      setUploadError(getDocumentApiError(error).message);
    } finally {
      activeUploadRef.current = false;
      setUploadState("idle");
      setUploadProgress(null);
    }
  }

  return (
    <section className="upload-page" aria-labelledby="upload-page-title">
      <div className="upload-page__header">
        <p className="upload-page__eyebrow">Document upload</p>
        <h1 id="upload-page-title">Upload a document</h1>
        <p>
          Choose a PDF, DOCX, TXT, or CSV file. The file is checked before any
          upload request is allowed.
        </p>
      </div>

      <form
        aria-busy={isUploading}
        className="upload-page__form"
        onSubmit={handleSubmit}
      >
        <UploadBox
          disabled={isUploading}
          label="Select document"
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
          onFileReject={handleFileReject}
        />

        {validationError ? (
          <p className="upload-page__error" role="alert">
            {validationError}
          </p>
        ) : null}

        {uploadError ? (
          <p className="upload-page__error" role="alert">
            {uploadError}
          </p>
        ) : null}

        {uploadResult ? (
          <div className="upload-page__success" role="status">
            <p className="upload-page__success-title">
              Upload completed for {uploadResult.file_name}.
            </p>
            <div className="upload-page__success-summary">
              <span>Current backend status:</span>
              <StatusBadge status={uploadResult.status} />
            </div>
            <p className="upload-page__success-copy">
              {getUploadStatusMessage(uploadResult)}
            </p>
          </div>
        ) : null}

        {isUploading ? (
          <div className="upload-page__progress" role="status">
            <p className="upload-page__status">
              {uploadProgress?.isComputable && uploadProgress.percent !== null
                ? `Uploading selected document: ${uploadProgress.percent}%`
                : "Uploading selected document..."}
            </p>
            {uploadProgress?.isComputable && uploadProgress.percent !== null ? (
              <progress
                aria-label="Upload progress"
                max={100}
                value={uploadProgress.percent}
              >
                {uploadProgress.percent}%
              </progress>
            ) : (
              <progress aria-label="Upload progress" />
            )}
          </div>
        ) : null}

        <button type="submit" disabled={!canUpload}>
          {isUploading ? "Uploading..." : "Upload document"}
        </button>
      </form>

      <section className="upload-page__recent" aria-labelledby="recent-documents-title">
        <div className="upload-page__recent-header">
          <div>
            <p className="upload-page__eyebrow">Recent feedback</p>
            <h2 id="recent-documents-title">Recent documents</h2>
          </div>
          <p className="upload-page__recent-copy">
            The latest uploaded documents appear here after the backend list
            refresh completes.
          </p>
        </div>

        {recentDocumentsState === "loading" ? (
          <p className="upload-page__recent-message" role="status">
            Loading recent documents...
          </p>
        ) : null}

        {recentDocumentsState === "error" && recentDocumentsError ? (
          <p className="upload-page__recent-error" role="alert">
            {recentDocumentsError}
          </p>
        ) : null}

        {recentDocumentsState === "ready" && !hasRecentDocuments ? (
          <p className="upload-page__recent-empty" role="status">
            No documents have been uploaded yet.
          </p>
        ) : null}

        {recentDocumentsState === "ready" && hasRecentDocuments ? (
          <div className="upload-page__recent-list">
            {recentDocuments.map((document) => (
              <DocumentCard key={document.id} document={document} />
            ))}
          </div>
        ) : null}
      </section>
    </section>
  );
}
