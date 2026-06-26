import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
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
  realtimeNodes: string[];
}

const MOCK_CHAT_ANSWER =
  "Hello, please upload or select document to begin ask me";

const NODE_METADATA: Record<string, { label: string; desc: string }> = {
  prepare_query: { label: "Query Preparation", desc: "Initializing request parameters and configurations..." },
  plan_query: { label: "Query Planning", desc: "Formulating search strategies and subqueries..." },
  resolve_relation_scope: { label: "Relation Scoping", desc: "Analyzing cross-document links and contexts..." },
  retrieve_candidates: { label: "Hybrid Retrieval", desc: "Fetching candidates from vector store and database indexes..." },
  fuse_candidates: { label: "Reciprocal Fusion", desc: "Merging search paths and calculating reciprocal rank scores..." },
  rerank_candidates: { label: "Re-ranking Chunks", desc: "Evaluating semantic relevance scores via Jina AI reranker..." },
  expand_context: { label: "Context Expansion", desc: "Assembling adjacent sections and boundary chunks..." },
  generate_answer: { label: "Drafting Synthesis", desc: "Generating answer chunks with model-local citation keys..." },
  validate_citations: { label: "Citation Validation", desc: "Verifying inline citations against exact context sources..." },
  verify_grounding: { label: "Grounding Gate", desc: "Running verifier model to prevent factual hallucinations..." },
  regenerate_answer: { label: "Regeneration Step", desc: "Re-synthesizing answer with corrective verifier feedback..." },
  finalize_answer: { label: "Finalization", desc: "Polishing answer and packaging validated citations..." },
  save_message_optional: { label: "Database Logging", desc: "Persisting grounded Q&A interaction to historic messages..." }
};

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
  realtimeNodes,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [displayedNodes, setDisplayedNodes] = useState<string[]>([]);
  const [pendingNodesQueue, setPendingNodesQueue] = useState<string[]>([]);
  const [pendingResponse, setPendingResponse] = useState<ChatResponse | null>(null);
  const [displayLoading, setDisplayLoading] = useState(false);

  // Trigger loading when submit begins
  useEffect(() => {
    if (isSubmitting) {
      setDisplayLoading(true);
      setDisplayedNodes(["prepare_query"]);
      setPendingNodesQueue([]);
      setPendingResponse(null);
    }
  }, [isSubmitting]);

  // Load new realtime nodes into queue
  useEffect(() => {
    if (!displayLoading) return;
    
    const existing = new Set([...displayedNodes, ...pendingNodesQueue]);
    const nextQueue = realtimeNodes.filter(node => !existing.has(node) && node in NODE_METADATA);
    
    if (nextQueue.length > 0) {
      setPendingNodesQueue(prev => [...prev, ...nextQueue]);
    }
  }, [realtimeNodes, displayLoading, displayedNodes, pendingNodesQueue]);

  // Dequeue node every 2 seconds
  useEffect(() => {
    if (!displayLoading) return;

    const timer = setInterval(() => {
      setPendingNodesQueue((prevQueue) => {
        if (prevQueue.length > 0) {
          const [nextNode, ...remaining] = prevQueue;
          setDisplayedNodes((prevDisplayed) => [...prevDisplayed, nextNode]);
          return remaining;
        }
        return prevQueue;
      });
    }, 2000);

    return () => clearInterval(timer);
  }, [displayLoading]);

  // Capture response once it returns from backend
  useEffect(() => {
    if (!isSubmitting && response && (response.answer || response.sources?.length > 0)) {
      setPendingResponse(response);
    }
  }, [isSubmitting, response]);

  // Complete loading and reveal response after all nodes are rendered and response is ready
  const allNodesRendered = pendingNodesQueue.length === 0 && 
                           realtimeNodes.length > 0 && 
                           displayedNodes.length === realtimeNodes.filter(n => n in NODE_METADATA).length;

  useEffect(() => {
    if (allNodesRendered && pendingResponse && displayLoading) {
      const timeout = setTimeout(() => {
        setDisplayLoading(false);
      }, 2000);
      return () => clearTimeout(timeout);
    }
  }, [allNodesRendered, pendingResponse, displayLoading]);

  // Handle sudden error from backend - interrupt loading immediately
  useEffect(() => {
    if (error) {
      setDisplayLoading(false);
      setPendingResponse(null);
    }
  }, [error]);

  const showLoader = displayLoading;
  const showResponse = !displayLoading && (response.answer || response.sources?.length > 0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [response, isSubmitting, displayedNodes, displayLoading]);

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
  
  // Render up to 4 most recent displayed nodes
  const nodesToRender = displayedNodes.slice(-4);

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
                {showLoader ? (
                  <div className="chat-bubble-content" style={{ background: "transparent", border: "none", boxShadow: "none", backdropFilter: "none", padding: 0 }}>
                    <div className="rag-loading-container">
                      <div className="rag-loading-header">
                        <span className="spinner small" aria-hidden="true" />
                        <span className="rag-loading-title">RAG Engine Workflow Trace...</span>
                      </div>
                      <div className="rag-steps-list">
                        {nodesToRender.map((nodeName, idx) => {
                          const step = NODE_METADATA[nodeName];
                          if (!step) return null;

                          const isLastInRender = idx === nodesToRender.length - 1;
                          const isActuallyLastNode = displayedNodes[displayedNodes.length - 1] === nodeName;
                          
                          let stepClass = "rag-step-item";
                          let icon = "circle";
                          
                          if (isActuallyLastNode && !(allNodesRendered && pendingResponse)) {
                            stepClass += " active";
                            icon = "progress_activity";
                          } else {
                            stepClass += " completed";
                            icon = "check_circle";
                          }

                          return (
                            <div key={nodeName} className={stepClass}>
                              <span className="material-symbols-outlined rag-step-icon">{icon}</span>
                              <div className="rag-step-details">
                                <span className="rag-step-label">{step.label}</span>
                                <span className="rag-step-desc">{step.desc}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ) : error ? (
                  <div className="chat-bubble-content" style={{ color: "var(--danger)", border: "1px solid var(--danger)" }}>
                    <span className="material-symbols-outlined" style={{ verticalAlign: "middle", marginRight: "6px" }}>error</span>
                    {error}
                  </div>
                ) : showResponse ? (
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
                ) : null}
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

