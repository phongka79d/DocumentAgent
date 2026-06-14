import { useEffect, useRef, useState } from "react";

import {
  deleteDocument,
  getDocumentApiError,
  getDocumentApiErrorMessage,
  listDocuments,
} from "../api/documents";
import { DocumentCard } from "../components/DocumentCard";
import type { DocumentListItem } from "../types/documents";

type DocumentListRequestState = "loading" | "ready" | "error";

type DocumentListErrorState = {
  kind: "connection" | "backend" | "request";
  message: string;
} | null;

export function DocumentListPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [requestState, setRequestState] =
    useState<DocumentListRequestState>("loading");
  const [requestError, setRequestError] = useState<DocumentListErrorState>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(
    null,
  );
  const [deleteErrors, setDeleteErrors] = useState<Record<string, string>>({});
  const deletingDocumentIdRef = useRef<string | null>(null);
  const deletedDocumentIdsRef = useRef(new Set<string>());
  const requestInFlightRef = useRef(false);
  const latestRequestIdRef = useRef(0);
  const documentsRef = useRef<DocumentListItem[]>([]);

  function setVisibleDocuments(nextDocuments: DocumentListItem[]) {
    documentsRef.current = nextDocuments;
    setDocuments(nextDocuments);
  }

  useEffect(() => {
    let isCurrentRequest = true;

    async function loadDocuments() {
      const requestId = latestRequestIdRef.current + 1;
      latestRequestIdRef.current = requestId;
      requestInFlightRef.current = true;
      setRequestState("loading");
      setRequestError(null);

      try {
        const response = await listDocuments();

        if (!isCurrentRequest || latestRequestIdRef.current !== requestId) {
          return;
        }

      setVisibleDocuments(
        response.documents.filter(
          (document) => !deletedDocumentIdsRef.current.has(document.id),
        ),
      );
        setRequestState("ready");
      } catch (error) {
        if (!isCurrentRequest || latestRequestIdRef.current !== requestId) {
          return;
        }

        const apiError = getDocumentApiError(error);

        setRequestError({
          kind: apiError.kind,
          message: apiError.message,
        });
        setRequestState((currentRequestState) =>
          currentRequestState === "ready" && documentsRef.current.length > 0
            ? "ready"
            : "error",
        );
      } finally {
        if (latestRequestIdRef.current === requestId) {
          requestInFlightRef.current = false;
        }
      }
    }

    void loadDocuments();

    return () => {
      isCurrentRequest = false;
    };
  }, []);

  const hasDocuments = documents.length > 0;
  const isInitialLoading = requestState === "loading" && !hasDocuments;
  const isEmpty = requestState === "ready" && !hasDocuments && !requestError;
  const isBlockingError = requestState === "error" && requestError;
  const isStaleListError = requestState === "ready" && hasDocuments && requestError;
  const isListRequestInFlight = requestState === "loading" || isRefreshing;
  const errorTitle =
    requestError?.kind === "connection"
      ? "Connection error"
      : "Document list error";
  const refreshButtonLabel = isRefreshing ? "Refreshing..." : "Refresh";

  async function refreshDocuments() {
    if (requestInFlightRef.current) {
      return;
    }

    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    requestInFlightRef.current = true;
    setIsRefreshing(true);
    setRequestState(documentsRef.current.length > 0 ? "ready" : "loading");
    setRequestError(null);

    try {
      const response = await listDocuments();

      if (latestRequestIdRef.current !== requestId) {
        return;
      }

        setVisibleDocuments(
          response.documents.filter(
            (document) => !deletedDocumentIdsRef.current.has(document.id),
          ),
        );
      setRequestState("ready");
    } catch (error) {
      if (latestRequestIdRef.current !== requestId) {
        return;
      }

      const apiError = getDocumentApiError(error);

      setRequestError({
        kind: apiError.kind,
        message: apiError.message,
      });
      setRequestState(documentsRef.current.length > 0 ? "ready" : "error");
    } finally {
      if (latestRequestIdRef.current === requestId) {
        requestInFlightRef.current = false;
        setIsRefreshing(false);
      }
    }
  }

  async function handleDelete(document: DocumentListItem) {
    if (deletingDocumentIdRef.current !== null) {
      setDeleteErrors((currentDeleteErrors) => ({
        ...currentDeleteErrors,
        [document.id]: "Another document deletion is already in progress.",
      }));
      throw new Error("Another document deletion is already in progress.");
    }

    deletingDocumentIdRef.current = document.id;
    setDeletingDocumentId(document.id);
    setDeleteErrors((currentDeleteErrors) => ({
      ...currentDeleteErrors,
      [document.id]: "",
    }));

    try {
      const response = await deleteDocument(document.id);

      if (!response.deleted || response.document_id !== document.id) {
        throw new Error("Unexpected document deletion response.");
      }

      deletedDocumentIdsRef.current.add(document.id);
      const nextDocuments = documentsRef.current.filter(
        (item) => item.id !== document.id,
      );
      setVisibleDocuments(nextDocuments);
    } catch (error) {
      setDeleteErrors((currentDeleteErrors) => ({
        ...currentDeleteErrors,
        [document.id]: getDocumentApiErrorMessage(error),
      }));
      throw error;
    } finally {
      deletingDocumentIdRef.current = null;
      setDeletingDocumentId(null);
    }
  }

  return (
    <section className="document-list-page" aria-labelledby="document-list-title">
      <div className="document-list-page__header">
        <div>
          <p className="document-list-page__eyebrow">Document library</p>
          <h1 id="document-list-title">Documents</h1>
        </div>
        <button
          className="document-list-page__refresh"
          type="button"
          onClick={refreshDocuments}
          disabled={isListRequestInFlight}
          aria-busy={isRefreshing}
        >
          {refreshButtonLabel}
        </button>
      </div>

      {isInitialLoading ? (
        <p className="document-list-page__message" role="status">
          Loading documents...
        </p>
      ) : null}

      {isRefreshing ? (
        <p className="document-list-page__message" role="status">
          Refreshing document statuses...
        </p>
      ) : null}

      {isBlockingError || isStaleListError ? (
        <div className="document-list-page__error" role="alert">
          <p className="document-list-page__error-title">{errorTitle}</p>
          <p className="document-list-page__error-copy">{requestError.message}</p>
          {isStaleListError ? (
            <p className="document-list-page__error-copy">
              Showing the last loaded document list.
            </p>
          ) : null}
          <button
            type="button"
            onClick={refreshDocuments}
            disabled={isListRequestInFlight}
          >
            {isRefreshing ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : null}

      {isEmpty ? (
        <div className="document-list-page__empty" role="status">
          <p className="document-list-page__empty-title">No documents yet</p>
          <p className="document-list-page__empty-copy">
            Uploaded documents will appear here after the backend returns them.
          </p>
        </div>
      ) : null}

      {hasDocuments ? (
        <div className="document-list-page__list">
          {documents.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              isDeleting={deletingDocumentId === document.id}
              deleteError={deleteErrors[document.id] || null}
              onDelete={handleDelete}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
