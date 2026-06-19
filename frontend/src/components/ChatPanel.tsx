import { type FormEvent } from "react";
import type {
  ChatResponse,
  DocumentChunk,
  DocumentResponse,
  SourceCitation,
} from "../api/types";
import ChunkViewerPanel from "./ChunkViewerPanel";
import SourceList from "./SourceList";

interface ChatPanelProps {
  question: string;
  response: ChatResponse;
  error: string | null;
  isSubmitting: boolean;
  readyDocuments: DocumentResponse[];
  selectedDocumentIds: string[];
  selectedSource: SourceCitation | null;
  selectedChunk: DocumentChunk | null;
  isSourceLoading: boolean;
  sourceError: string | null;
  hasPreviousChunk: boolean;
  hasNextChunk: boolean;
  onQuestionChange: (value: string) => void;
  onToggleDocument: (documentId: string) => void;
  onSubmit: () => Promise<void>;
  onSelectSource: (source: SourceCitation) => void;
  onViewPreviousChunk: () => void;
  onViewNextChunk: () => void;
}

export default function ChatPanel({
  error,
  isSubmitting,
  isSourceLoading,
  onQuestionChange,
  onSelectSource,
  onSubmit,
  onToggleDocument,
  onViewNextChunk,
  onViewPreviousChunk,
  question,
  readyDocuments,
  response,
  selectedChunk,
  selectedDocumentIds,
  selectedSource,
  sourceError,
  hasNextChunk,
  hasPreviousChunk,
}: ChatPanelProps) {
  const selectedCount = selectedDocumentIds.length;
  const hasReadyDocuments = readyDocuments.length > 0;
  const statusMessage = error ?? (isSubmitting ? "Sending" : null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting || !question.trim()) {
      return;
    }

    void onSubmit();
  }

  return (
    <section className="panel chat-panel" aria-label="Chat">
      <div className="panel-heading">
        <h2>Chat</h2>
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Question</span>
          <textarea
            className="chat-question"
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder="What does this document say about pricing?"
            rows={5}
            disabled={isSubmitting}
          />
        </label>

        <div className="chat-documents" aria-label="Ready documents">
          <div className="chat-documents__header">
            <span className="field-label">Documents</span>
            <span className="chat-documents__count">
              {selectedCount > 0 ? `${selectedCount} selected` : "All documents"}
            </span>
          </div>

          {hasReadyDocuments ? (
            <div className="chat-documents__list" role="group">
              {readyDocuments.map((document) => {
                const checked = selectedDocumentIds.includes(document.id);

                return (
                  <label key={document.id} className="chat-document-option">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleDocument(document.id)}
                      disabled={isSubmitting}
                    />
                    <span
                      className="chat-document-option__label"
                      title={document.file_name}
                    >
                      {document.file_name}
                    </span>
                  </label>
                );
              })}
            </div>
          ) : (
            <div className="chat-documents__empty">No ready documents</div>
          )}
        </div>

        <div className="chat-footer">
          <button
            className="button button--primary"
            type="submit"
            disabled={isSubmitting || !question.trim()}
            aria-busy={isSubmitting}
          >
            {isSubmitting ? (
              <span className="button-spinner" aria-hidden="true" />
            ) : null}
            <span>{isSubmitting ? "Sending" : "Ask"}</span>
          </button>

          <div
            className={`chat-status ${
              error
                ? "chat-status--error"
                : isSubmitting
                  ? "chat-status--loading"
                  : "chat-status--idle"
            }`}
            aria-live="polite"
          >
            {statusMessage}
          </div>
        </div>
      </form>

      <div className="chat-response" aria-live="polite">
        <section className="chat-response__section">
          <span className="field-label">Answer</span>
          <p className="chat-answer">{response.answer}</p>
        </section>

        <section className="chat-response__section">
          <span className="field-label">Sources</span>
          <SourceList
            sources={response.sources}
            selectedSourceChunkId={selectedSource?.chunk_id ?? null}
            onSelectSource={onSelectSource}
          />
        </section>

        <section className="chat-response__section">
          <span className="field-label">Source viewer</span>
          <ChunkViewerPanel
            selectedSource={selectedSource}
            selectedChunk={selectedChunk}
            isLoading={isSourceLoading}
            error={sourceError}
            hasPreviousChunk={hasPreviousChunk}
            hasNextChunk={hasNextChunk}
            onViewPreviousChunk={onViewPreviousChunk}
            onViewNextChunk={onViewNextChunk}
          />
        </section>
      </div>
    </section>
  );
}
