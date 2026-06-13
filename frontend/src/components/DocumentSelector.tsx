import { useEffect, useMemo, useState } from "react";

import { getDocumentApiErrorMessage, listDocuments } from "../api/documents";
import type { DocumentListItem } from "../types/documents";

type DocumentSelectorProps = {
  selectedDocumentIds: string[];
  onSelectedDocumentIdsChange: (documentIds: string[]) => void;
  documents?: DocumentListItem[];
  disabled?: boolean;
  isLoading?: boolean;
  errorMessage?: string | null;
  validationMessage?: string | null;
  label?: string;
};

type InternalLoadState = "idle" | "loading" | "ready" | "error";

export type DocumentSelectionValidation = {
  selectedReadyDocumentIds: string[];
  hasReadyDocuments: boolean;
  isValid: boolean;
  message: string | null;
};

export type ReadyDocumentSelectionState = {
  selectedDocumentIds: string[];
  selectedReadyDocumentIds: string[];
  setSelectedDocumentIds: (documentIds: string[]) => void;
  clearSelectedDocumentIds: () => void;
  validation: DocumentSelectionValidation;
};

export const DOCUMENT_SELECTION_REQUIRED_MESSAGE =
  "Select at least one ready document before asking a question.";

export const NO_READY_DOCUMENTS_MESSAGE =
  "No ready documents are available for chat.";

function formatChunkCount(chunkCount: number) {
  return `${chunkCount.toLocaleString()} ${chunkCount === 1 ? "chunk" : "chunks"}`;
}

export function getReadyDocumentIds(
  documents: DocumentListItem[],
  selectedDocumentIds: string[],
) {
  const readyDocumentIds = new Set(
    documents
      .filter((document) => document.status === "ready")
      .map((document) => document.id),
  );

  return selectedDocumentIds.filter((documentId) =>
    readyDocumentIds.has(documentId),
  );
}

export function validateReadyDocumentSelection(
  documents: DocumentListItem[],
  selectedDocumentIds: string[],
): DocumentSelectionValidation {
  const selectedReadyDocumentIds = getReadyDocumentIds(
    documents,
    selectedDocumentIds,
  );
  const hasReadyDocuments = documents.some(
    (document) => document.status === "ready",
  );

  if (!hasReadyDocuments) {
    return {
      selectedReadyDocumentIds,
      hasReadyDocuments,
      isValid: false,
      message: NO_READY_DOCUMENTS_MESSAGE,
    };
  }

  if (selectedReadyDocumentIds.length === 0) {
    return {
      selectedReadyDocumentIds,
      hasReadyDocuments,
      isValid: false,
      message: DOCUMENT_SELECTION_REQUIRED_MESSAGE,
    };
  }

  return {
    selectedReadyDocumentIds,
    hasReadyDocuments,
    isValid: true,
    message: null,
  };
}

export function useReadyDocumentSelection(
  documents: DocumentListItem[],
): ReadyDocumentSelectionState {
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const validation = useMemo(
    () => validateReadyDocumentSelection(documents, selectedDocumentIds),
    [documents, selectedDocumentIds],
  );

  return {
    selectedDocumentIds,
    selectedReadyDocumentIds: validation.selectedReadyDocumentIds,
    setSelectedDocumentIds,
    clearSelectedDocumentIds: () => setSelectedDocumentIds([]),
    validation,
  };
}

function getUnavailableReason(document: DocumentListItem) {
  switch (document.status) {
    case "uploaded":
      return "Uploaded, not ready";
    case "processing":
      return "Processing";
    case "failed":
      return "Failed";
    case "ready":
      return "Ready";
  }
}

export function DocumentSelector({
  selectedDocumentIds,
  onSelectedDocumentIdsChange,
  documents,
  disabled = false,
  isLoading = false,
  errorMessage = null,
  validationMessage = null,
  label = "Documents",
}: DocumentSelectorProps) {
  const shouldLoadDocuments = documents === undefined;
  const [loadedDocuments, setLoadedDocuments] = useState<DocumentListItem[]>([]);
  const [loadState, setLoadState] = useState<InternalLoadState>("idle");
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!shouldLoadDocuments) {
      return;
    }

    let isActive = true;

    async function loadReadyDocuments() {
      setLoadState("loading");
      setLoadErrorMessage(null);

      try {
        const response = await listDocuments();

        if (!isActive) {
          return;
        }

        setLoadedDocuments(response.documents);
        setLoadState("ready");
      } catch (error) {
        if (!isActive) {
          return;
        }

        setLoadedDocuments([]);
        setLoadErrorMessage(getDocumentApiErrorMessage(error));
        setLoadState("error");
      }
    }

    void loadReadyDocuments();

    return () => {
      isActive = false;
    };
  }, [shouldLoadDocuments]);

  const visibleDocuments = documents ?? loadedDocuments;
  const readyDocumentIds = useMemo(() => {
    const selectedReadyIds = getReadyDocumentIds(
      visibleDocuments,
      visibleDocuments.map((document) => document.id),
    );

    return new Set(selectedReadyIds);
  }, [visibleDocuments]);
  const readyDocuments = visibleDocuments.filter(
    (document) => document.status === "ready",
  );
  const selectedReadyDocumentIds = useMemo(
    () => getReadyDocumentIds(visibleDocuments, selectedDocumentIds),
    [selectedDocumentIds, visibleDocuments],
  );
  const hasDocuments = visibleDocuments.length > 0;
  const hasReadyDocuments = readyDocuments.length > 0;
  const loading = isLoading || (shouldLoadDocuments && loadState === "loading");
  const resolvedErrorMessage = errorMessage ?? loadErrorMessage;

  useEffect(() => {
    if (!hasDocuments && !selectedDocumentIds.length) {
      return;
    }

    if (selectedReadyDocumentIds.length !== selectedDocumentIds.length) {
      onSelectedDocumentIdsChange(selectedReadyDocumentIds);
    }
  }, [
    hasDocuments,
    onSelectedDocumentIdsChange,
    selectedDocumentIds,
    selectedReadyDocumentIds,
  ]);

  function toggleDocument(documentId: string) {
    if (!readyDocumentIds.has(documentId) || disabled || loading) {
      return;
    }

    if (selectedReadyDocumentIds.includes(documentId)) {
      onSelectedDocumentIdsChange(
        selectedReadyDocumentIds.filter((selectedId) => selectedId !== documentId),
      );
      return;
    }

    onSelectedDocumentIdsChange([...selectedReadyDocumentIds, documentId]);
  }

  return (
    <section className="document-selector" aria-labelledby="document-selector-title">
      <div className="document-selector__header">
        <h2 id="document-selector-title">{label}</h2>
        <span className="document-selector__count" aria-live="polite">
          {selectedReadyDocumentIds.length} selected
        </span>
      </div>

      {loading ? (
        <p className="document-selector__message">Loading documents...</p>
      ) : null}

      {!loading && resolvedErrorMessage ? (
        <p className="document-selector__error" role="alert">
          {resolvedErrorMessage}
        </p>
      ) : null}

      {!loading && !resolvedErrorMessage && validationMessage ? (
        <p className="document-selector__validation" role="alert">
          {validationMessage}
        </p>
      ) : null}

      {!loading && !resolvedErrorMessage && !hasDocuments ? (
        <p className="document-selector__message">
          No documents have been uploaded yet.
        </p>
      ) : null}

      {!loading && !resolvedErrorMessage && hasDocuments && !hasReadyDocuments ? (
        <p className="document-selector__message">
          No ready documents are available for chat.
        </p>
      ) : null}

      {!loading && !resolvedErrorMessage && hasDocuments ? (
        <ul className="document-selector__list" aria-label="Document choices">
          {visibleDocuments.map((document) => {
            const isReady = document.status === "ready";
            const isSelected = selectedReadyDocumentIds.includes(document.id);
            const unavailableReason = getUnavailableReason(document);

            return (
              <li
                className={
                  isReady
                    ? "document-selector__item"
                    : "document-selector__item document-selector__item--unavailable"
                }
                key={document.id}
              >
                <label className="document-selector__option">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={!isReady || disabled || loading}
                    onChange={() => toggleDocument(document.id)}
                  />
                  <span className="document-selector__document">
                    <span className="document-selector__name">
                      {document.file_name}
                    </span>
                    <span className="document-selector__meta">
                      {document.file_type} - {formatChunkCount(document.chunk_count)}
                    </span>
                  </span>
                  <span className="document-selector__status">
                    {unavailableReason}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
