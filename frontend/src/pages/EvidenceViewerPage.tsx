import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  getAgentRunEvidence,
  getAgentRunsApiErrorMessage,
} from "../api/agentRuns";
import { EvidencePanel } from "../components/EvidencePanel";
import type { AgentRunEvidence } from "../types/chat";

type EvidenceLoadState = "loading" | "ready" | "error" | "invalid";

export function EvidenceViewerPage() {
  const { agentRunId } = useParams<{ agentRunId: string }>();
  const normalizedAgentRunId = agentRunId?.trim() ?? "";
  const [loadState, setLoadState] = useState<EvidenceLoadState>(
    normalizedAgentRunId ? "loading" : "invalid",
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<AgentRunEvidence | null>(null);

  useEffect(() => {
    if (!normalizedAgentRunId) {
      setLoadState("invalid");
      setErrorMessage(null);
      setEvidence(null);
      return;
    }

    let isActive = true;

    async function loadEvidence() {
      setLoadState("loading");
      setErrorMessage(null);
      setEvidence(null);

      try {
        const response = await getAgentRunEvidence(normalizedAgentRunId);

        if (!isActive) {
          return;
        }

        setEvidence(response);
        setLoadState("ready");
      } catch (error) {
        if (!isActive) {
          return;
        }

        setErrorMessage(getAgentRunsApiErrorMessage(error));
        setLoadState("error");
      }
    }

    void loadEvidence();

    return () => {
      isActive = false;
    };
  }, [normalizedAgentRunId]);

  return (
    <section
      className="evidence-viewer-page"
      aria-labelledby="evidence-viewer-title"
    >
      <header className="evidence-viewer-page__header">
        <p className="evidence-viewer-page__eyebrow">Agent run inspection</p>
        <h1 id="evidence-viewer-title">Evidence viewer</h1>
        <p>Review the verified and rejected evidence for this answer.</p>
      </header>

      {loadState === "invalid" ? (
        <p className="evidence-viewer-page__error" role="alert">
          A valid agent run ID is required to load evidence.
        </p>
      ) : null}

      {loadState === "loading" ? (
        <p className="evidence-viewer-page__message" role="status">
          Loading evidence...
        </p>
      ) : null}

      {loadState === "error" && errorMessage ? (
        <p className="evidence-viewer-page__error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      {loadState === "ready" && evidence ? (
        <EvidencePanel evidence={evidence} />
      ) : null}
    </section>
  );
}
