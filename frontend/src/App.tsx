import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_API_BASE_URL, apiClient } from "./api/client";
import type { ChatRequest, ChatResponse, DocumentResponse } from "./api/types";
import ChatPanel from "./components/ChatPanel";
import DocumentList from "./components/DocumentList";
import UploadPanel from "./components/UploadPanel";

type DocumentAction = "index" | "reindex" | "delete";

const MOCK_CHAT_RESPONSE = {
  answer:
    "Pricing is organized by usage tier. The document ties the base plan to volume and shows that higher tiers reduce the unit cost as usage grows.",
  sources: [
    {
      document_id: "mock-document-1",
      chunk_id: "mock-chunk-12",
      file_name: "report.pdf",
      chunk_index: 12,
      page_start: 3,
      page_end: 4,
      heading: null,
      qdrant_score: 0.78,
      rerank_score: 0.91,
    },
    {
      document_id: "mock-document-2",
      chunk_id: "mock-chunk-2",
      file_name: "summary.md",
      chunk_index: 2,
      page_start: null,
      page_end: null,
      heading: null,
      qdrant_score: 0.71,
      rerank_score: 0.88,
    },
  ],
} satisfies ChatResponse;

function resolveApiBaseUrl(rawValue: string | undefined): string {
  const value = rawValue?.trim();
  if (!value) {
    return DEFAULT_API_BASE_URL;
  }

  return value.replace(/\/+$/, "");
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}

export default function App() {
  const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const apiBaseUrl = resolveApiBaseUrl(rawApiBaseUrl);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [chatResponse, setChatResponse] =
    useState<ChatResponse>(MOCK_CHAT_RESPONSE);
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true);
  const [isRefreshingDocuments, setIsRefreshingDocuments] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    documentId: string;
    kind: DocumentAction;
  } | null>(null);

  const readyDocuments = useMemo(
    () => documents.filter((document) => document.status === "ready"),
    [documents],
  );

  const selectedReadyDocumentIds = useMemo(() => {
    if (selectedDocumentIds.length === 0 || readyDocuments.length === 0) {
      return [];
    }

    const readyDocumentIdSet = new Set(
      readyDocuments.map((document) => document.id),
    );

    return selectedDocumentIds.filter((documentId) =>
      readyDocumentIdSet.has(documentId),
    );
  }, [readyDocuments, selectedDocumentIds]);

  useEffect(() => {
    if (selectedDocumentIds.length === 0) {
      return;
    }

    const readyDocumentIdSet = new Set(
      readyDocuments.map((document) => document.id),
    );
    const nextSelectedDocumentIds = selectedDocumentIds.filter((documentId) =>
      readyDocumentIdSet.has(documentId),
    );

    if (nextSelectedDocumentIds.length !== selectedDocumentIds.length) {
      setSelectedDocumentIds(nextSelectedDocumentIds);
    }
  }, [readyDocuments, selectedDocumentIds]);

  const loadDocuments = useCallback(
    async (options: { background?: boolean } = {}) => {
      const { background = false } = options;

      if (background) {
        setIsRefreshingDocuments(true);
      } else {
        setIsLoadingDocuments(true);
      }

      setDocumentError(null);

      try {
        const response = await apiClient.listDocuments();
        setDocuments(Array.isArray(response.documents) ? response.documents : []);
      } catch (error) {
        setDocumentError(
          getErrorMessage(error, "Unable to load documents."),
        );
      } finally {
        if (background) {
          setIsRefreshingDocuments(false);
        } else {
          setIsLoadingDocuments(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const handleUpload = useCallback(
    async (file: File) => {
      if (isUploading || pendingAction) {
        return;
      }

      setIsUploading(true);
      setUploadError(null);
      setUploadResult(null);

      try {
        const response = await apiClient.uploadDocument(file);
        setUploadResult(response.duplicate ? "Duplicate upload" : "Uploaded");
        await loadDocuments({ background: true });
      } catch (error) {
        setUploadError(
          getErrorMessage(error, "Unable to upload document."),
        );
      } finally {
        setIsUploading(false);
      }
    },
    [isUploading, loadDocuments, pendingAction],
  );

  const handleDocumentAction = useCallback(
    async (documentId: string, kind: DocumentAction) => {
      if (isUploading || pendingAction) {
        return;
      }

      setPendingAction({ documentId, kind });
      setDocumentError(null);

      try {
        if (kind === "index") {
          await apiClient.indexDocument(documentId);
        } else if (kind === "reindex") {
          await apiClient.reindexDocument(documentId);
        } else {
          await apiClient.deleteDocument(documentId);
          setDocuments((current) =>
            current.filter((document) => document.id !== documentId),
          );
        }

        await loadDocuments({ background: true });
      } catch (error) {
        setDocumentError(
          getErrorMessage(error, `Unable to ${kind === "reindex" ? "re-index" : kind} document.`),
        );
      } finally {
        setPendingAction(null);
      }
    },
    [isUploading, loadDocuments, pendingAction],
  );

  const handleQuestionChange = useCallback((value: string) => {
    setQuestion(value);
    setChatError(null);
  }, []);

  const handleToggleSelectedDocument = useCallback((documentId: string) => {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((currentDocumentId) => currentDocumentId !== documentId)
        : [...current, documentId],
    );
  }, []);

  const handleChatSubmit = useCallback(async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isSendingChat) {
      return;
    }

    setIsSendingChat(true);
    setChatError(null);

    try {
      const request: ChatRequest = {
        question: trimmedQuestion,
        save_message: true,
      };

      if (selectedReadyDocumentIds.length > 0) {
        request.document_ids = selectedReadyDocumentIds;
      }

      const response = await apiClient.sendChatMessage(request);
      setChatResponse(response);
    } catch (error) {
      setChatError(getErrorMessage(error, "Unable to send question."));
    } finally {
      setIsSendingChat(false);
    }
  }, [isSendingChat, question, selectedReadyDocumentIds]);

  const refreshDocuments = useCallback(async () => {
    await loadDocuments({ background: true });
  }, [loadDocuments]);

  const isDocumentActionBusy = isUploading || pendingAction !== null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <h1>RagDocument</h1>
        </div>

        <div className="api-chip" title={apiBaseUrl}>
          <span className="status-dot" aria-hidden="true" />
          <span>{apiBaseUrl}</span>
        </div>
      </header>

      <main className="workspace">
        <div className="workspace-grid">
          <div className="workspace-column">
            <UploadPanel
              error={uploadError}
              isUploading={isUploading}
              onUpload={handleUpload}
              result={uploadResult}
            />

            <DocumentList
              documents={documents}
              error={documentError}
              isBusy={isDocumentActionBusy}
              isLoading={isLoadingDocuments}
              isRefreshing={isRefreshingDocuments}
              onDelete={(documentId) =>
                handleDocumentAction(documentId, "delete")
              }
              onIndex={(documentId) => handleDocumentAction(documentId, "index")}
              onRefresh={refreshDocuments}
              onReindex={(documentId) =>
                handleDocumentAction(documentId, "reindex")
              }
              pendingAction={pendingAction?.kind ?? null}
              pendingDocumentId={pendingAction?.documentId ?? null}
            />
          </div>

          <ChatPanel
            error={chatError}
            isSubmitting={isSendingChat}
            onQuestionChange={handleQuestionChange}
            onSubmit={handleChatSubmit}
            onToggleDocument={handleToggleSelectedDocument}
            question={question}
            readyDocuments={readyDocuments}
            response={chatResponse}
            selectedDocumentIds={selectedReadyDocumentIds}
          />
        </div>
      </main>
    </div>
  );
}
