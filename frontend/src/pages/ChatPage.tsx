import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  getAgentRunEvidence,
  getAgentRunsApiErrorMessage,
} from "../api/agentRuns";
import { askQuestion, getChatApiErrorMessage } from "../api/chat";
import { getDocumentApiErrorMessage, listDocuments } from "../api/documents";
import { AnswerPanel } from "../components/AnswerPanel";
import { ChatBox } from "../components/ChatBox";
import {
  DocumentSelector,
  useReadyDocumentSelection,
} from "../components/DocumentSelector";
import { EvidencePanel } from "../components/EvidencePanel";
import type { AgentRunEvidence, AskQuestionResponse } from "../types/chat";
import type { DocumentListItem } from "../types/documents";

type DocumentLoadState = "loading" | "ready" | "error";

export function ChatPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [documentLoadState, setDocumentLoadState] =
    useState<DocumentLoadState>("loading");
  const [documentErrorMessage, setDocumentErrorMessage] = useState<
    string | null
  >(null);
  const [question, setQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectionValidationMessage, setSelectionValidationMessage] = useState<
    string | null
  >(null);
  const [chatErrorMessage, setChatErrorMessage] = useState<string | null>(null);
  const [latestResponse, setLatestResponse] =
    useState<AskQuestionResponse | null>(null);
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [isEvidenceLoading, setIsEvidenceLoading] = useState(false);
  const [evidenceErrorMessage, setEvidenceErrorMessage] = useState<
    string | null
  >(null);
  const [evidence, setEvidence] = useState<AgentRunEvidence | null>(null);
  const latestEvidenceRequestIdRef = useRef(0);
  const selection = useReadyDocumentSelection(documents);

  useEffect(() => {
    let isActive = true;

    async function loadDocuments() {
      setDocumentLoadState("loading");
      setDocumentErrorMessage(null);

      try {
        const response = await listDocuments();

        if (!isActive) {
          return;
        }

        setDocuments(response.documents);
        setDocumentLoadState("ready");
      } catch (error) {
        if (!isActive) {
          return;
        }

        setDocuments([]);
        setDocumentErrorMessage(getDocumentApiErrorMessage(error));
        setDocumentLoadState("error");
      }
    }

    void loadDocuments();

    return () => {
      isActive = false;
    };
  }, []);

  function handleSelectedDocumentIdsChange(documentIds: string[]) {
    selection.setSelectedDocumentIds(documentIds);
    setSelectionValidationMessage(null);
  }

  async function handleSubmit(trimmedQuestion: string) {
    const currentSelection = selection.validation;

    if (!currentSelection.isValid) {
      setSelectionValidationMessage(currentSelection.message);
      return;
    }

    setIsSubmitting(true);
    setSelectionValidationMessage(null);
    setChatErrorMessage(null);

    try {
      const response = await askQuestion({
        question: trimmedQuestion,
        document_ids: currentSelection.selectedReadyDocumentIds,
      });

      latestEvidenceRequestIdRef.current += 1;
      setLatestResponse(response);
      setIsEvidenceOpen(false);
      setIsEvidenceLoading(false);
      setEvidenceErrorMessage(null);
      setEvidence(null);
    } catch (error) {
      setChatErrorMessage(getChatApiErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function loadEvidence(agentRunId: string) {
    const requestId = latestEvidenceRequestIdRef.current + 1;
    latestEvidenceRequestIdRef.current = requestId;
    setIsEvidenceLoading(true);
    setEvidenceErrorMessage(null);

    try {
      const response = await getAgentRunEvidence(agentRunId);

      if (latestEvidenceRequestIdRef.current !== requestId) {
        return;
      }

      setEvidence(response);
    } catch (error) {
      if (latestEvidenceRequestIdRef.current !== requestId) {
        return;
      }

      setEvidenceErrorMessage(getAgentRunsApiErrorMessage(error));
    } finally {
      if (latestEvidenceRequestIdRef.current === requestId) {
        setIsEvidenceLoading(false);
      }
    }
  }

  function handleEvidenceToggle() {
    if (!latestResponse) {
      return;
    }

    const nextOpenState = !isEvidenceOpen;
    setIsEvidenceOpen(nextOpenState);

    if (
      nextOpenState &&
      !evidence &&
      !isEvidenceLoading &&
      !evidenceErrorMessage
    ) {
      void loadEvidence(latestResponse.agent_run_id);
    }
  }

  function retryEvidenceLoad() {
    if (!latestResponse || isEvidenceLoading) {
      return;
    }

    void loadEvidence(latestResponse.agent_run_id);
  }

  const isDocumentLoading = documentLoadState === "loading";
  const isDocumentLoadBlocked = documentLoadState === "error";
  const hasReadyDocuments = selection.validation.hasReadyDocuments;
  const isChatDisabled =
    isDocumentLoading || isDocumentLoadBlocked || !hasReadyDocuments;
  const latestAgentLogsPath = latestResponse?.agent_run_id.trim()
    ? `/agent-logs/${encodeURIComponent(latestResponse.agent_run_id.trim())}`
    : null;

  return (
    <section className="chat-page" aria-labelledby="chat-page-title">
      <header className="chat-page__header">
        <p className="chat-page__eyebrow">Document question answering</p>
        <h1 id="chat-page-title">Chat with documents</h1>
        <p>
          Select ready documents and ask a question grounded in their content.
        </p>
      </header>

      <div className="chat-page__workspace">
        <DocumentSelector
          documents={documents}
          disabled={isSubmitting}
          errorMessage={documentErrorMessage}
          isLoading={isDocumentLoading}
          onSelectedDocumentIdsChange={handleSelectedDocumentIdsChange}
          selectedDocumentIds={selection.selectedDocumentIds}
          validationMessage={selectionValidationMessage}
        />

        <ChatBox
          disabled={isChatDisabled}
          isSubmitting={isSubmitting}
          onQuestionChange={setQuestion}
          onSubmit={handleSubmit}
          question={question}
        />
      </div>

      {chatErrorMessage ? (
        <p className="chat-page__error" role="alert">
          {chatErrorMessage}
        </p>
      ) : null}

      {latestResponse ? (
        <>
          <AnswerPanel
            agentRunId={latestResponse.agent_run_id}
            answer={latestResponse.answer}
            citations={latestResponse.citations}
            confidence={latestResponse.confidence}
          />
          <section
            className="chat-page__evidence"
            aria-labelledby="chat-page-evidence-title"
          >
            <div className="chat-page__evidence-header">
              <h2 id="chat-page-evidence-title">Answer evidence</h2>
              <div className="chat-page__answer-actions">
                {latestAgentLogsPath ? (
                  <Link
                    className="chat-page__agent-logs-link"
                    to={latestAgentLogsPath}
                  >
                    Inspect agent logs
                  </Link>
                ) : null}
                <button
                  className="chat-page__evidence-toggle"
                  type="button"
                  aria-expanded={isEvidenceOpen}
                  onClick={handleEvidenceToggle}
                >
                  {isEvidenceOpen ? "Hide evidence" : "View evidence"}
                </button>
              </div>
            </div>

            {isEvidenceOpen ? (
              <div className="chat-page__evidence-content">
                {isEvidenceLoading ? (
                  <p className="chat-page__evidence-message" role="status">
                    Loading evidence...
                  </p>
                ) : null}

                {evidenceErrorMessage ? (
                  <div className="chat-page__evidence-error" role="alert">
                    <p>{evidenceErrorMessage}</p>
                    <button
                      type="button"
                      disabled={isEvidenceLoading}
                      onClick={retryEvidenceLoad}
                    >
                      Retry evidence
                    </button>
                  </div>
                ) : null}

                {evidence ? <EvidencePanel evidence={evidence} /> : null}
              </div>
            ) : null}
          </section>
        </>
      ) : (
        <p className="chat-page__empty-answer">
          Submit a question to see the grounded answer and citations.
        </p>
      )}
    </section>
  );
}
