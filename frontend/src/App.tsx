import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_API_BASE_URL, apiClient } from "./api/client";
import type {
  ChatRequest,
  ChatResponse,
  DocumentChunk,
  DocumentResponse,
  MessageHistoryItem,
  SourceCitation,
} from "./api/types";
import ChatPanel from "./components/ChatPanel";
import DocumentList from "./components/DocumentList";
import MessageHistoryPanel from "./components/MessageHistoryPanel";
import UploadPanel from "./components/UploadPanel";

type DocumentAction = "index" | "reindex" | "delete";
type ChunkLoadStatus = "idle" | "loading" | "ready" | "error";

interface ChunkLoadState {
  status: ChunkLoadStatus;
  error: string | null;
}

const INITIAL_CHUNK_LOAD_STATE: ChunkLoadState = {
  status: "idle",
  error: null,
};

const MESSAGE_HISTORY_LIMIT = 25;

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
  const [selectedSource, setSelectedSource] = useState<SourceCitation | null>(
    null,
  );
  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(
    null,
  );
  const [documentChunkCache, setDocumentChunkCache] = useState<
    Record<string, DocumentChunk[]>
  >({});
  const [documentChunkState, setDocumentChunkState] = useState<
    Record<string, ChunkLoadState>
  >({});
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true);
  const [isRefreshingDocuments, setIsRefreshingDocuments] = useState(false);
  const [messageHistory, setMessageHistory] = useState<MessageHistoryItem[]>([]);
  const [messageHistoryError, setMessageHistoryError] = useState<string | null>(
    null,
  );
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(
    null,
  );
  const [isLoadingMessageHistory, setIsLoadingMessageHistory] = useState(false);
  const [hasLoadedMessageHistory, setHasLoadedMessageHistory] = useState(false);
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

  const selectedSourceLoadState = selectedSource
    ? documentChunkState[selectedSource.document_id] ?? INITIAL_CHUNK_LOAD_STATE
    : INITIAL_CHUNK_LOAD_STATE;

  const selectedDocumentChunks = useMemo(() => {
    if (!selectedSource) {
      return null;
    }

    return documentChunkCache[selectedSource.document_id] ?? null;
  }, [documentChunkCache, selectedSource]);

  const selectedChunk = useMemo(() => {
    if (!selectedDocumentChunks || selectedChunkIndex === null) {
      return null;
    }

    return (
      selectedDocumentChunks.find(
        (chunk) => chunk.chunk_index === selectedChunkIndex,
      ) ?? null
    );
  }, [selectedChunkIndex, selectedDocumentChunks]);

  const previousChunk = useMemo(() => {
    if (!selectedChunk || !selectedDocumentChunks) {
      return null;
    }

    return (
      selectedDocumentChunks.find(
        (chunk) => chunk.chunk_index === selectedChunk.chunk_index - 1,
      ) ?? null
    );
  }, [selectedChunk, selectedDocumentChunks]);

  const nextChunk = useMemo(() => {
    if (!selectedChunk || !selectedDocumentChunks) {
      return null;
    }

    return (
      selectedDocumentChunks.find(
        (chunk) => chunk.chunk_index === selectedChunk.chunk_index + 1,
      ) ?? null
    );
  }, [selectedChunk, selectedDocumentChunks]);

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

  useEffect(() => {
    setSelectedSource(null);
    setSelectedChunkIndex(null);
  }, [chatResponse]);

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
        setDocumentError(getErrorMessage(error, "Unable to load documents."));
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

  const loadDocumentChunks = useCallback(async (documentId: string) => {
    setDocumentChunkState((current) => ({
      ...current,
      [documentId]: {
        status: "loading",
        error: null,
      },
    }));

    try {
      const response = await apiClient.getDocumentChunks(documentId);
      setDocumentChunkCache((current) => ({
        ...current,
        [documentId]: Array.isArray(response.chunks) ? response.chunks : [],
      }));
      setDocumentChunkState((current) => ({
        ...current,
        [documentId]: {
          status: "ready",
          error: null,
        },
      }));
    } catch (error) {
      setDocumentChunkState((current) => ({
        ...current,
        [documentId]: {
          status: "error",
          error: getErrorMessage(error, "Unable to load source."),
        },
      }));
    }
  }, []);

  const loadMessageHistory = useCallback(async () => {
    setIsLoadingMessageHistory(true);
    setMessageHistoryError(null);

    try {
      const response = await apiClient.listMessages(MESSAGE_HISTORY_LIMIT);
      const nextMessages = Array.isArray(response.messages)
        ? response.messages
        : [];

      setMessageHistory(nextMessages);
      setSelectedMessageId((current) =>
        nextMessages.some((message) => message.id === current) ? current : null,
      );
    } catch (error) {
      setMessageHistoryError(
        getErrorMessage(error, "Unable to load message history."),
      );
    } finally {
      setHasLoadedMessageHistory(true);
      setIsLoadingMessageHistory(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (isLoadingDocuments || hasLoadedMessageHistory) {
      return;
    }

    void loadMessageHistory();
  }, [hasLoadedMessageHistory, isLoadingDocuments, loadMessageHistory]);

  useEffect(() => {
    if (!selectedSource) {
      return;
    }

    const documentId = selectedSource.document_id;
    const chunkState = documentChunkState[documentId] ?? INITIAL_CHUNK_LOAD_STATE;

    if (chunkState.status !== "idle") {
      return;
    }

    void loadDocumentChunks(documentId);
  }, [documentChunkState, loadDocumentChunks, selectedSource]);

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
        setUploadError(getErrorMessage(error, "Unable to upload document."));
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
          setDocumentChunkCache((current) => {
            const nextCache = { ...current };
            delete nextCache[documentId];
            return nextCache;
          });
          setDocumentChunkState((current) => {
            const nextState = { ...current };
            delete nextState[documentId];
            return nextState;
          });
          setSelectedSource((current) =>
            current?.document_id === documentId ? null : current,
          );
          setSelectedChunkIndex((current) =>
            selectedSource?.document_id === documentId ? null : current,
          );
        }

        await loadDocuments({ background: true });
      } catch (error) {
        setDocumentError(
          getErrorMessage(
            error,
            `Unable to ${kind === "reindex" ? "re-index" : kind} document.`,
          ),
        );
      } finally {
        setPendingAction(null);
      }
    },
    [isUploading, loadDocuments, pendingAction, selectedSource],
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

  const handleSelectSource = useCallback((source: SourceCitation) => {
    setSelectedSource({ ...source });
    setSelectedChunkIndex(source.chunk_index);
    setDocumentChunkState((current) => {
      const existingState = current[source.document_id];
      if (!existingState || existingState.status !== "error") {
        return current;
      }

      return {
        ...current,
        [source.document_id]: INITIAL_CHUNK_LOAD_STATE,
      };
    });
  }, []);

  const handleViewPreviousChunk = useCallback(() => {
    if (!previousChunk) {
      return;
    }

    setSelectedChunkIndex(previousChunk.chunk_index);
  }, [previousChunk]);

  const handleViewNextChunk = useCallback(() => {
    if (!nextChunk) {
      return;
    }

    setSelectedChunkIndex(nextChunk.chunk_index);
  }, [nextChunk]);

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
      setSelectedMessageId(null);
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

  const handleRefreshMessageHistory = useCallback(async () => {
    await loadMessageHistory();
  }, [loadMessageHistory]);

  const handleSelectMessageHistoryItem = useCallback(
    (message: MessageHistoryItem) => {
      setSelectedMessageId(message.id);
      setChatError(null);
      setChatResponse({
        answer: message.answer,
        sources: Array.isArray(message.sources) ? message.sources : [],
      });
    },
    [],
  );

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

            <MessageHistoryPanel
              error={messageHistoryError}
              hasLoaded={hasLoadedMessageHistory}
              isLoading={isLoadingMessageHistory}
              messages={messageHistory}
              onRefresh={handleRefreshMessageHistory}
              onSelectMessage={handleSelectMessageHistoryItem}
              selectedMessageId={selectedMessageId}
            />
          </div>

          <ChatPanel
            error={chatError}
            isSubmitting={isSendingChat}
            isSourceLoading={selectedSourceLoadState.status === "loading"}
            onQuestionChange={handleQuestionChange}
            onSelectSource={handleSelectSource}
            onSubmit={handleChatSubmit}
            onToggleDocument={handleToggleSelectedDocument}
            onViewNextChunk={handleViewNextChunk}
            onViewPreviousChunk={handleViewPreviousChunk}
            question={question}
            readyDocuments={readyDocuments}
            response={chatResponse}
            selectedChunk={selectedChunk}
            selectedDocumentIds={selectedReadyDocumentIds}
            selectedSource={selectedSource}
            sourceError={
              selectedSourceLoadState.status === "error"
                ? selectedSourceLoadState.error
                : null
            }
            hasNextChunk={nextChunk !== null}
            hasPreviousChunk={previousChunk !== null}
          />
        </div>
      </main>
    </div>
  );
}
