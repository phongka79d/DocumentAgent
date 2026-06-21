import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { DEFAULT_API_BASE_URL, apiClient } from "./api/client";
import type {
  ChatRequest,
  ChatResponse,
  DocumentChunk,
  DocumentResponse,
  MessageHistoryItem,
  RetrievalFilters,
  SourceCitation,
} from "./api/types";
import ChatPanel from "./components/ChatPanel";
import DocumentList from "./components/DocumentList";
import MessageHistoryPanel from "./components/MessageHistoryPanel";
import ChunkViewerPanel from "./components/ChunkViewerPanel";
import {
  EMPTY_RETRIEVAL_FILTERS,
  type RetrievalFilterState,
} from "./components/RetrievalFiltersPanel";

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
    "Hello! i'm DocuRAG, how can i help you today?",
  sources: [],
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

function splitFilterText(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter((part, index, parts) => part.length > 0 && parts.indexOf(part) === index);
}

function parsePageFilter(value: string): number | undefined {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return undefined;
  }

  const pageNumber = Number(trimmedValue);
  if (!Number.isInteger(pageNumber) || pageNumber < 0) {
    return Number.NaN;
  }

  return pageNumber;
}

function getRetrievalFilterValidationMessage(
  filters: RetrievalFilterState,
): string | null {
  const pageStart = parsePageFilter(filters.pageStart);
  const pageEnd = parsePageFilter(filters.pageEnd);

  if (Number.isNaN(pageStart) || Number.isNaN(pageEnd)) {
    return "Page filters must be whole numbers 0 or greater.";
  }

  if (pageStart !== undefined && pageEnd !== undefined && pageStart > pageEnd) {
    return "Start page must be less than or equal to end page.";
  }

  return null;
}

function buildRetrievalFilters(
  filters: RetrievalFilterState,
): RetrievalFilters | undefined {
  const requestFilters: RetrievalFilters = {};
  const mimeTypes = splitFilterText(filters.mimeTypes);
  const sectionPath = splitFilterText(filters.sectionPath);
  const heading = filters.heading.trim();
  const pageStart = parsePageFilter(filters.pageStart);
  const pageEnd = parsePageFilter(filters.pageEnd);

  if (mimeTypes.length > 0) {
    requestFilters.mime_types = mimeTypes;
  }
  if (heading) {
    requestFilters.heading = heading;
  }
  if (sectionPath.length > 0) {
    requestFilters.section_path = sectionPath;
  }
  if (pageStart !== undefined && !Number.isNaN(pageStart)) {
    requestFilters.page_start = pageStart;
  }
  if (pageEnd !== undefined && !Number.isNaN(pageEnd)) {
    requestFilters.page_end = pageEnd;
  }

  return Object.keys(requestFilters).length > 0 ? requestFilters : undefined;
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

  // New UI states
  const [activeView, setActiveView] = useState<"chat" | "documents" | "history">("chat");
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [activeQuestion, setActiveQuestion] = useState("");
  const [retrievalFilters, setRetrievalFilters] =
    useState<RetrievalFilterState>(EMPTY_RETRIEVAL_FILTERS);

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

  const retrievalFilterValidationMessage = useMemo(
    () => getRetrievalFilterValidationMessage(retrievalFilters),
    [retrievalFilters],
  );

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
    if (!trimmedQuestion || isSendingChat || retrievalFilterValidationMessage) {
      return;
    }

    setIsSendingChat(true);
    setChatError(null);
    setActiveQuestion(trimmedQuestion);

    try {
      const request: ChatRequest = {
        question: trimmedQuestion,
        save_message: true,
      };

      if (selectedReadyDocumentIds.length > 0) {
        request.document_ids = selectedReadyDocumentIds;
      }

      const filters = buildRetrievalFilters(retrievalFilters);
      if (filters) {
        request.filters = filters;
      }

      const response = await apiClient.sendChatMessage(request);
      setSelectedMessageId(null);
      setChatResponse(response);
      setQuestion("");
    } catch (error) {
      setChatError(getErrorMessage(error, "Unable to send question."));
    } finally {
      setIsSendingChat(false);
    }
  }, [
    isSendingChat,
    question,
    retrievalFilterValidationMessage,
    retrievalFilters,
    selectedReadyDocumentIds,
  ]);

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
      setActiveQuestion(message.question);
      setChatResponse({
        answer: message.answer,
        sources: Array.isArray(message.sources) ? message.sources : [],
      });
      setActiveView("chat"); // Switch back to chat to view the selected answer
    },
    [],
  );

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      void handleUpload(file);
    }
  };

  const handleNewChat = () => {
    setQuestion("");
    setActiveQuestion("");
    setChatResponse(MOCK_CHAT_RESPONSE);
    setSelectedSource(null);
    setSelectedChunkIndex(null);
    setActiveView("chat");
    setIsMobileSidebarOpen(false);
  };

  // Client-side filtering of documents based on Search Term
  const filteredDocuments = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return documents;
    return documents.filter((doc) =>
      doc.file_name.toLowerCase().includes(term)
    );
  }, [documents, searchTerm]);

  const isDocumentActionBusy = isUploading || pendingAction !== null;

  return (
    <div className="app-layout">
      {/* Sidebar Overlay for mobile screen */}
      <div
        className={`app-sidebar-overlay ${isMobileSidebarOpen ? "open" : ""}`}
        onClick={() => setIsMobileSidebarOpen(false)}
      />

      {/* Sidebar Panel */}
      <aside className={`app-sidebar ${isMobileSidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <h1>RagDocument</h1>
          <p className="sidebar-subtitle">AI Research Assistant</p>
        </div>

        {/* Upload hidden input and styled button */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
          style={{ display: "none" }}
          onChange={handleFileChange}
          disabled={isUploading}
        />
        <button
          className="btn-primary mb-8"
          onClick={handleUploadClick}
          disabled={isUploading}
        >
          <span className="material-symbols-outlined">add</span>
          Upload Document
        </button>

        {/* Sidebar upload feedback */}
        {isUploading || uploadError || uploadResult ? (
          <div className="sidebar-upload-status">
            <div className="sidebar-upload-text">
              {isUploading ? "Uploading file..." : uploadResult || "Upload ready"}
            </div>
            <div className={`sidebar-upload-feedback ${isUploading ? "loading" : uploadError ? "error" : "success"}`}>
              {isUploading ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  <span>Sending to Server</span>
                </>
              ) : uploadError ? (
                uploadError
              ) : (
                "File processed!"
              )}
            </div>
          </div>
        ) : null}

        {/* Sidebar Navigation Options */}
        <nav className="sidebar-menu">
          <button
            className={`menu-item ${activeView === "chat" ? "active" : ""}`}
            onClick={() => {
              setActiveView("chat");
              setIsMobileSidebarOpen(false);
            }}
          >
            <span className="material-symbols-outlined">chat</span>
            Active Chat
          </button>

          <button
            className={`menu-item ${activeView === "documents" ? "active" : ""}`}
            onClick={() => {
              setActiveView("documents");
              setIsMobileSidebarOpen(false);
            }}
          >
            <span className="material-symbols-outlined">description</span>
            All Documents
          </button>

          <button
            className={`menu-item ${activeView === "history" ? "active" : ""}`}
            onClick={() => {
              setActiveView("history");
              setIsMobileSidebarOpen(false);
            }}
          >
            <span className="material-symbols-outlined">history</span>
            Recent Research
          </button>
        </nav>

        {/* Chat Document Selection checkboxes in Sidebar */}
        {activeView === "chat" && readyDocuments.length > 0 ? (
          <div className="sidebar-sources-section">
            <span className="sidebar-sources-label">Chat Over Documents</span>
            {readyDocuments.map((doc) => {
              const isChecked = selectedDocumentIds.includes(doc.id);
              return (
                <label key={doc.id} className="sidebar-source-item">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleToggleSelectedDocument(doc.id)}
                    disabled={isSendingChat}
                  />
                  <span className="sidebar-source-name" title={doc.file_name}>
                    {doc.file_name}
                  </span>
                </label>
              );
            })}
          </div>
        ) : null}

        {/* Static sidebar items matching layout style */}
        <div className="menu-footer">
          <button className="menu-item" onClick={handleNewChat}>
            <span className="material-symbols-outlined">restart_alt</span>
            Reset Conversation
          </button>
        </div>
      </aside>

      {/* Main Canvas Area */}
      <main className="main-area">
        {/* Topbar/Header */}
        <header className="app-topbar">
          <div className="flex items-center gap-4 flex-1">
            <button
              className="mobile-sidebar-toggle"
              onClick={() => setIsMobileSidebarOpen(true)}
              aria-label="Open sidebar menu"
            >
              <span className="material-symbols-outlined">menu</span>
            </button>
            <div className="topbar-search-container">
              <span className="material-symbols-outlined search-icon">search</span>
              <input
                className="search-input"
                type="text"
                placeholder="Search across documents..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          <div className="topbar-actions">
            <div className="topbar-api-chip" title={apiBaseUrl}>
              <span className="api-dot" aria-hidden="true" />
              <span>{apiBaseUrl}</span>
            </div>

            <button className="topbar-action-button" aria-label="Notifications">
              <span className="material-symbols-outlined">notifications</span>
            </button>

            <button
              className="topbar-action-button"
              onClick={() => setActiveView("documents")}
              aria-label="Settings"
            >
              <span className="material-symbols-outlined">settings</span>
            </button>

            <div className="topbar-avatar">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDcCw0_qGkLU5bX1wJiMYH1_xOr5JPaOLk2JIEEioy-ac2VmNMbCm5eZ1Na2iOw7gTfFe2rfZZAOic56GQaQEiINDiQWysoSWrlhWwSNa-xPFHiWWBls9I0WIAZ4tB8wkZrc4ZGWLgKfKidT45E-X4VVTszd532gAtF0KopoJNWn2nycKs_Kn9FR2ERxzRDLBhDDbnaF2vjlzAXGo0bdXi8amQI_AIbKZ6y4uu8T8vWuo4IVmwOfsWejoYlj2n9uOKFN9EN4-4UZqcC"
                alt="User headshot avatar"
              />
            </div>
          </div>
        </header>

        {/* Central Component Switcher */}
        <div className="content-canvas">
          {activeView === "chat" ? (
            <ChatPanel
              error={chatError}
              isSubmitting={isSendingChat}
              isSourceLoading={selectedSourceLoadState.status === "loading"}
              onQuestionChange={handleQuestionChange}
              onRetrievalFiltersChange={setRetrievalFilters}
              onSelectSource={handleSelectSource}
              onSubmit={handleChatSubmit}
              onToggleDocument={handleToggleSelectedDocument}
              onViewNextChunk={handleViewNextChunk}
              onViewPreviousChunk={handleViewPreviousChunk}
              question={question}
              activeQuestion={activeQuestion}
              retrievalFilters={retrievalFilters}
              filterValidationMessage={retrievalFilterValidationMessage}
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
          ) : activeView === "documents" ? (
            <div>
              <div className="documents-view-header">
                <h2>Document Management</h2>
                <button
                  className="refresh-button"
                  onClick={refreshDocuments}
                  disabled={isLoadingDocuments || isRefreshingDocuments || isDocumentActionBusy}
                >
                  {isRefreshingDocuments ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined">refresh</span>
                  )}
                  <span>{isRefreshingDocuments ? "Refreshing" : "Refresh List"}</span>
                </button>
              </div>

              <DocumentList
                documents={filteredDocuments}
                error={documentError}
                isBusy={isDocumentActionBusy}
                isLoading={isLoadingDocuments}
                isRefreshing={isRefreshingDocuments}
                onDelete={(documentId) => handleDocumentAction(documentId, "delete")}
                onIndex={(documentId) => handleDocumentAction(documentId, "index")}
                onRefresh={refreshDocuments}
                onReindex={(documentId) => handleDocumentAction(documentId, "reindex")}
                pendingAction={pendingAction?.kind ?? null}
                pendingDocumentId={pendingAction?.documentId ?? null}
              />
            </div>
          ) : (
            <div>
              <div className="documents-view-header">
                <h2>Recent Research History</h2>
                <button
                  className="refresh-button"
                  onClick={handleRefreshMessageHistory}
                  disabled={isLoadingMessageHistory}
                >
                  {isLoadingMessageHistory && hasLoadedMessageHistory ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined">refresh</span>
                  )}
                  <span>Refresh History</span>
                </button>
              </div>

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
          )}
        </div>
      </main>

      {/* Right Sidebar: Document Preview (Collapsible) */}
      <aside className={`app-preview-panel ${selectedSource ? "open" : ""}`}>
        <div className="preview-panel-header">
          <div className="preview-panel-header-title">
            <span className="material-symbols-outlined">description</span>
            <h2>{selectedSource?.file_name ?? "Document Preview"}</h2>
          </div>
          <button
            className="preview-close-button"
            onClick={() => setSelectedSource(null)}
            aria-label="Close preview panel"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="preview-panel-content">
          <ChunkViewerPanel
            selectedSource={selectedSource}
            selectedChunk={selectedChunk}
            isLoading={selectedSourceLoadState.status === "loading"}
            error={
              selectedSourceLoadState.status === "error"
                ? selectedSourceLoadState.error
                : null
            }
            hasPreviousChunk={previousChunk !== null}
            hasNextChunk={nextChunk !== null}
            onViewPreviousChunk={handleViewPreviousChunk}
            onViewNextChunk={handleViewNextChunk}
          />
        </div>
      </aside>
    </div>
  );
}
