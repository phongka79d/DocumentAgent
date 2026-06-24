import { useCallback, useEffect, useRef } from "react";
import { DEFAULT_API_BASE_URL } from "./api/client";
import type { MessageHistoryItem } from "./api/types";
import { useChat } from "./hooks/useChat";
import { useChunks } from "./hooks/useChunks";
import { useDocuments } from "./hooks/useDocuments";
import { useMessageHistory } from "./hooks/useMessageHistory";
import { useUiState } from "./hooks/useUiState";
import ChatPanel from "./components/ChatPanel";
import DocumentList from "./components/DocumentList";
import MessageHistoryPanel from "./components/MessageHistoryPanel";
import ReferencesDrawer from "./components/ReferencesDrawer";

function resolveApiBaseUrl(rawValue: string | undefined): string {
  const value = rawValue?.trim();
  if (!value) return DEFAULT_API_BASE_URL;
  return value.replace(/\/+$/, "");
}

export default function App() {
  const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const apiBaseUrl = resolveApiBaseUrl(rawApiBaseUrl);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const docs = useDocuments();
  const chunks = useChunks();
  const chat = useChat();
  const history = useMessageHistory();
  const ui = useUiState();

  // Message history: load after documents finish loading
  useEffect(() => {
    if (docs.isLoading || history.hasLoaded) return;
    void history.load();
  }, [docs.isLoading, history.hasLoaded, history.load]);

  // Clear chunk selection when chat response changes
  useEffect(() => {
    chunks.clearSelection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.response]);

  const handleSelectMessageHistoryItem = useCallback(
    (message: MessageHistoryItem) => {
      history.selectMessage(message);
      chat.displayResponse(
        {
          answer: message.answer,
          sources: Array.isArray(message.sources) ? message.sources : [],
        },
        message.question,
      );
      ui.setActiveView("chat");
    },
    [history, chat, ui],
  );

  const handleNewChat = useCallback(() => {
    chat.reset();
    chunks.clearSelection();
    ui.setActiveView("chat");
    ui.closeSidebar();
  }, [chat, chunks, ui]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      void docs.uploadDocument(file);
    }
  };

  return (
    <div className="app-layout">
      <div
        className={`app-sidebar-overlay ${ui.isMobileSidebarOpen ? "open" : ""}`}
        onClick={ui.closeSidebar}
      />

      <aside className={`app-sidebar ${ui.isMobileSidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <h1>RagDocument</h1>
          <p className="sidebar-subtitle">AI Research Assistant</p>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
          style={{ display: "none" }}
          onChange={handleFileChange}
          disabled={docs.isUploading}
        />
        <button
          className="btn-primary mb-8"
          onClick={handleUploadClick}
          disabled={docs.isUploading}
        >
          <span className="material-symbols-outlined">add</span>
          Upload Document
        </button>

        {docs.isUploading || docs.uploadError || docs.uploadResult ? (
          <div className="sidebar-upload-status">
            <div className="sidebar-upload-text">
              {docs.isUploading ? "Uploading file..." : docs.uploadResult || "Upload ready"}
            </div>
            <div
              className={`sidebar-upload-feedback ${docs.isUploading ? "loading" : docs.uploadError ? "error" : "success"}`}
            >
              {docs.isUploading ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  <span>Sending to Server</span>
                </>
              ) : docs.uploadError ? (
                docs.uploadError
              ) : (
                "File processed!"
              )}
            </div>
          </div>
        ) : null}

        <nav className="sidebar-menu">
          <button
            className={`menu-item ${ui.activeView === "chat" ? "active" : ""}`}
            onClick={() => {
              ui.setActiveView("chat");
              ui.closeSidebar();
            }}
          >
            <span className="material-symbols-outlined">chat</span>
            Active Chat
          </button>
          <button
            className={`menu-item ${ui.activeView === "documents" ? "active" : ""}`}
            onClick={() => {
              ui.setActiveView("documents");
              ui.closeSidebar();
            }}
          >
            <span className="material-symbols-outlined">description</span>
            All Documents
          </button>
          <button
            className={`menu-item ${ui.activeView === "history" ? "active" : ""}`}
            onClick={() => {
              ui.setActiveView("history");
              ui.closeSidebar();
            }}
          >
            <span className="material-symbols-outlined">history</span>
            Recent Research
          </button>
        </nav>

        {ui.activeView === "chat" && docs.readyDocuments.length > 0 ? (
          <div className="sidebar-sources-section">
            <span className="sidebar-sources-label">Chat Over Documents</span>
            {docs.readyDocuments.map((doc) => {
              const isChecked = docs.selectedDocumentIds.includes(doc.id);
              return (
                <label key={doc.id} className="sidebar-source-item">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => docs.toggleSelectedDocument(doc.id)}
                    disabled={chat.isSubmitting}
                  />
                  <span className="sidebar-source-name" title={doc.file_name}>
                    {doc.file_name}
                  </span>
                </label>
              );
            })}
          </div>
        ) : null}

        <div className="menu-footer">
          <button className="menu-item" onClick={handleNewChat}>
            <span className="material-symbols-outlined">restart_alt</span>
            Reset Conversation
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="app-topbar">
          <div className="flex items-center gap-4 flex-1">
            <button
              className="mobile-sidebar-toggle"
              onClick={ui.openSidebar}
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
                value={docs.searchTerm}
                onChange={(e) => docs.setSearchTerm(e.target.value)}
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
              onClick={() => ui.setActiveView("documents")}
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

        <div className="content-canvas">
          {ui.activeView === "chat" ? (
            <ChatPanel
              error={chat.error}
              isSubmitting={chat.isSubmitting}
              isSourceLoading={chunks.isLoading}
              onQuestionChange={chat.setQuestion}
              onSelectSource={chunks.selectSource}
              onSubmit={() => chat.submit(docs.selectedReadyDocumentIds)}
              onToggleDocument={docs.toggleSelectedDocument}
              onViewNextChunk={chunks.viewNextChunk}
              onViewPreviousChunk={chunks.viewPreviousChunk}
              question={chat.question}
              activeQuestion={chat.activeQuestion}
              readyDocuments={docs.readyDocuments}
              response={chat.response}
              selectedChunk={chunks.selectedChunk}
              selectedDocumentIds={docs.selectedReadyDocumentIds}
              selectedSource={chunks.selectedSource}
              sourceError={chunks.error}
              hasNextChunk={chunks.hasNextChunk}
              hasPreviousChunk={chunks.hasPreviousChunk}
            />
          ) : ui.activeView === "documents" ? (
            <div>
              <div className="documents-view-header">
                <h2>Document Management</h2>
                <button
                  className="refresh-button"
                  onClick={docs.refreshDocuments}
                  disabled={docs.isLoading || docs.isRefreshing || docs.isBusy}
                >
                  {docs.isRefreshing ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined">refresh</span>
                  )}
                  <span>{docs.isRefreshing ? "Refreshing" : "Refresh List"}</span>
                </button>
              </div>
              <DocumentList
                documents={docs.filteredDocuments}
                error={docs.error}
                isBusy={docs.isBusy}
                isLoading={docs.isLoading}
                isRefreshing={docs.isRefreshing}
                onDelete={(id) => docs.handleDocumentAction(id, "delete")}
                onIndex={(id) => docs.handleDocumentAction(id, "index")}
                onRefresh={docs.refreshDocuments}
                onReindex={(id) => docs.handleDocumentAction(id, "reindex")}
                pendingAction={docs.pendingAction?.kind ?? null}
                pendingDocumentId={docs.pendingAction?.documentId ?? null}
              />
            </div>
          ) : (
            <div>
              <div className="documents-view-header">
                <h2>Recent Research History</h2>
                <button
                  className="refresh-button"
                  onClick={history.refresh}
                  disabled={history.isLoading}
                >
                  {history.isLoading && history.hasLoaded ? (
                    <span className="spinner" aria-hidden="true" />
                  ) : (
                    <span className="material-symbols-outlined">refresh</span>
                  )}
                  <span>Refresh History</span>
                </button>
              </div>
              <MessageHistoryPanel
                error={history.error}
                hasLoaded={history.hasLoaded}
                isLoading={history.isLoading}
                messages={history.messages}
                onRefresh={history.refresh}
                onSelectMessage={handleSelectMessageHistoryItem}
                selectedMessageId={history.selectedMessageId}
              />
            </div>
          )}
        </div>
      </main>

      <ReferencesDrawer
        sources={chat.response.sources ?? []}
        selectedSource={chunks.selectedSource}
        selectedChunk={chunks.selectedChunk}
        isLoading={chunks.isLoading}
        error={chunks.error}
        hasPreviousChunk={chunks.hasPreviousChunk}
        hasNextChunk={chunks.hasNextChunk}
        onSelectSource={chunks.selectSource}
        onClose={chunks.clearSelection}
        onViewPreviousChunk={chunks.viewPreviousChunk}
        onViewNextChunk={chunks.viewNextChunk}
      />
    </div>
  );
}
