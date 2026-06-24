import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import type {
  ChatResponse,
  DocumentChunk,
  DocumentResponse,
  SourceCitation,
} from "../api/types";
import SourceList from "./SourceList";
import CitationText from "./CitationText";

interface ChatPanelProps {
  question: string;
  activeQuestion: string;
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

const MOCK_CHAT_ANSWER =
  "Hello, please upload or select document to begin ask me";

export default function ChatPanel({
  error,
  isSubmitting,
  onQuestionChange,
  onSelectSource,
  onSubmit,
  question,
  activeQuestion,
  response,
  selectedSource,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [response, isSubmitting]);

  // Auto-resize textarea height as content grows
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [question]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isSubmitting || !question.trim()) {
      return;
    }
    void onSubmit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSubmitting && question.trim()) {
        void onSubmit();
      }
    }
  }

  const hasAsked = Boolean(activeQuestion) || isSubmitting;

  return (
    <section className="chat-messages-wrapper" style={{ display: "flex", flexDirection: "column", height: "100%" }} aria-label="Chat Area">
      {/* Scrollable messages area */}
      <div className="chat-messages-container">
        {/* AI Greeting */}
        <div className="chat-bubble-row ai">
          <div className="chat-avatar">
            <span className="material-symbols-outlined">auto_awesome</span>
          </div>
          <div className="chat-bubble-body">
            <div className="chat-bubble-content">
              {MOCK_CHAT_ANSWER}
            </div>
          </div>
        </div>

        {/* User query and AI response */}
        {hasAsked && (
          <>
            {/* User message bubble */}
            <div className="chat-bubble-row user">
              <div className="chat-avatar">
                <span className="material-symbols-outlined">person</span>
              </div>
              <div className="chat-bubble-body">
                <div className="chat-bubble-content">
                  {activeQuestion}
                </div>
              </div>
            </div>

            {/* AI response bubble */}
            <div className="chat-bubble-row ai">
              <div className="chat-avatar">
                <span className="material-symbols-outlined">auto_awesome</span>
              </div>
              <div className="chat-bubble-body">
                {isSubmitting ? (
                  <div className="chat-bubble-content">
                    <span className="spinner" aria-hidden="true" />
                    <span style={{ marginLeft: "8px" }}>Analyzing documents...</span>
                  </div>
                ) : error ? (
                  <div className="chat-bubble-content" style={{ color: "var(--danger)", border: "1px solid var(--danger)" }}>
                    <span className="material-symbols-outlined" style={{ verticalAlign: "middle", marginRight: "6px" }}>error</span>
                    {error}
                  </div>
                ) : (
                  <>
                    <div className="chat-bubble-content chat-bubble-content-ai-response">
                      <CitationText
                        answer={response.answer}
                        sources={response.sources ?? []}
                        selectedSourceChunkId={selectedSource?.chunk_id ?? null}
                        onSelectSource={onSelectSource}
                      />
                    </div>

                    {response.sources && response.sources.length > 0 && (
                      <div className="chat-sources-container">
                        <span className="chat-sources-label">Sources & Citations</span>
                        <SourceList
                          sources={response.sources}
                          selectedSourceChunkId={selectedSource?.chunk_id ?? null}
                          onSelectSource={onSelectSource}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar area */}
      <form onSubmit={handleSubmit} className="chat-input-bar-container">
        <div className="chat-input-bar">
          <textarea
            ref={textareaRef}
            className="chat-input-textarea"
            value={question}
            onChange={(e) => onQuestionChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your indexed documents... (Enter to send, Shift+Enter for new line)"
            disabled={isSubmitting}
            aria-label="Ask a question"
          />
          <button
            className="chat-send-button"
            type="submit"
            disabled={isSubmitting || !question.trim()}
            aria-label="Send question"
          >
            {isSubmitting ? (
              <span className="spinner" aria-hidden="true" style={{ color: "var(--on-primary)" }} />
            ) : (
              <span className="material-symbols-outlined">send</span>
            )}
          </button>
        </div>
        <p className="chat-disclaimer">
          InsightDoc can make mistakes. Verify important information against the original documents.
        </p>
      </form>
    </section>
  );
}

