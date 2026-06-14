import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  getAgentRunLogs,
  getAgentRunsApiError,
  getAgentRunsApiErrorMessage,
} from "../api/agentRuns";
import { AgentLogViewer } from "../components/AgentLogViewer";
import { DeletionLogsPanel } from "../components/DeletionLogsPanel";
import type { AgentRunLogsResponse } from "../types/agentRuns";

type AgentLogsLoadState =
  | "idle"
  | "loading"
  | "success"
  | "empty-response"
  | "not-found"
  | "error";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function validateAgentRunId(agentRunId: string): string | null {
  if (agentRunId.length === 0) {
    return "Enter an agent run ID before loading logs.";
  }

  if (!UUID_PATTERN.test(agentRunId)) {
    return "Enter a valid agent run UUID.";
  }

  return null;
}

export function AgentLogsPage() {
  const { agentRunId } = useParams<{ agentRunId?: string }>();
  const navigate = useNavigate();
  const [agentRunIdInput, setAgentRunIdInput] = useState("");
  const [loadState, setLoadState] = useState<AgentLogsLoadState>("idle");
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null,
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [logsResponse, setLogsResponse] =
    useState<AgentRunLogsResponse | null>(null);
  const latestRequestIdRef = useRef(0);
  const lastAutoLoadedRouteIdRef = useRef<string | null>(null);

  const loadAgentRunLogs = useCallback(async (nextAgentRunId: string) => {
    const nextValidationMessage = validateAgentRunId(nextAgentRunId);

    if (nextValidationMessage) {
      setValidationMessage(nextValidationMessage);
      setErrorMessage(null);
      setLogsResponse(null);
      setLoadState("idle");
      return;
    }

    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    setAgentRunIdInput(nextAgentRunId);
    setValidationMessage(null);
    setErrorMessage(null);
    setLogsResponse(null);
    setLoadState("loading");

    try {
      const response = await getAgentRunLogs(nextAgentRunId);

      if (latestRequestIdRef.current !== requestId) {
        return;
      }

      setLogsResponse(response);
      setLoadState(
        response.steps.length === 0 ? "empty-response" : "success",
      );
    } catch (error) {
      if (latestRequestIdRef.current !== requestId) {
        return;
      }

      const apiError = getAgentRunsApiError(error);
      setErrorMessage(getAgentRunsApiErrorMessage(error));
      setLoadState(apiError.status === 404 ? "not-found" : "error");
    }
  }, []);

  useEffect(() => {
    if (agentRunId === undefined) {
      latestRequestIdRef.current += 1;
      lastAutoLoadedRouteIdRef.current = null;
      setAgentRunIdInput("");
      setValidationMessage(null);
      setErrorMessage(null);
      setLogsResponse(null);
      setLoadState("idle");
      return;
    }

    const trimmedRouteAgentRunId = agentRunId.trim();
    setAgentRunIdInput(trimmedRouteAgentRunId);

    const nextValidationMessage = validateAgentRunId(trimmedRouteAgentRunId);
    if (nextValidationMessage) {
      latestRequestIdRef.current += 1;
      lastAutoLoadedRouteIdRef.current = null;
      setValidationMessage(nextValidationMessage);
      setErrorMessage(null);
      setLogsResponse(null);
      setLoadState("idle");
      return;
    }

    if (lastAutoLoadedRouteIdRef.current === trimmedRouteAgentRunId) {
      return;
    }

    lastAutoLoadedRouteIdRef.current = trimmedRouteAgentRunId;
    void loadAgentRunLogs(trimmedRouteAgentRunId);
  }, [agentRunId, loadAgentRunLogs]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (loadState === "loading") {
      return;
    }

    const trimmedAgentRunId = agentRunIdInput.trim();
    const nextValidationMessage = validateAgentRunId(trimmedAgentRunId);

    if (nextValidationMessage) {
      setValidationMessage(nextValidationMessage);
      setErrorMessage(null);
      setLogsResponse(null);
      setLoadState("idle");
      return;
    }

    const nextPath = `/agent-logs/${encodeURIComponent(trimmedAgentRunId)}`;
    if (agentRunId === trimmedAgentRunId) {
      lastAutoLoadedRouteIdRef.current = trimmedAgentRunId;
      void loadAgentRunLogs(trimmedAgentRunId);
      return;
    }

    navigate(nextPath);
  }

  const isLoading = loadState === "loading";

  return (
    <section className="agent-logs-page" aria-labelledby="agent-logs-title">
      <header className="agent-logs-page__header">
        <p className="agent-logs-page__eyebrow">Agent run inspection</p>
        <h1 id="agent-logs-title">Agent Logs</h1>
        <p>
          Enter a known agent run ID to inspect persisted step inputs, outputs,
          statuses, timestamps, and errors.
        </p>
      </header>

      <form
        className="agent-logs-page__lookup"
        aria-busy={isLoading}
        onSubmit={handleSubmit}
      >
        <label className="agent-logs-page__label" htmlFor="agent-run-id">
          Agent run ID
        </label>
        <div className="agent-logs-page__controls">
          <input
            id="agent-run-id"
            className="agent-logs-page__input"
            type="text"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            value={agentRunIdInput}
            disabled={isLoading}
            aria-describedby="agent-logs-lookup-hint"
            onChange={(event) => {
              setAgentRunIdInput(event.target.value);
              setValidationMessage(null);
            }}
          />
          <button
            className="agent-logs-page__submit"
            type="submit"
            disabled={isLoading}
          >
            {isLoading ? "Loading..." : "Load logs"}
          </button>
        </div>
        <p id="agent-logs-lookup-hint" className="agent-logs-page__hint">
          UUID format is required. Blank and malformed IDs are blocked before a
          request is sent.
        </p>
      </form>

      {validationMessage ? (
        <p className="agent-logs-page__validation" role="alert">
          {validationMessage}
        </p>
      ) : null}

      {loadState === "idle" && !validationMessage ? (
        <p className="agent-logs-page__message">
          No run loaded. Submit a valid agent run UUID to inspect logs.
        </p>
      ) : null}

      {loadState === "loading" ? (
        <p className="agent-logs-page__message" role="status">
          Loading agent logs...
        </p>
      ) : null}

      {loadState === "not-found" ? (
        <p className="agent-logs-page__error" role="alert">
          {errorMessage ?? "No agent run was found for that ID."}
        </p>
      ) : null}

      {loadState === "error" ? (
        <p className="agent-logs-page__error" role="alert">
          {errorMessage ??
            "Unable to load agent logs. Confirm the backend is running and try again."}
        </p>
      ) : null}

      {loadState === "empty-response" && logsResponse ? (
        <section className="agent-logs-page__empty" role="status">
          <h2>No persisted steps</h2>
          <p>
            Run {logsResponse.agent_run_id} loaded, but the backend returned an
            empty steps array.
          </p>
        </section>
      ) : null}

      {loadState === "success" && logsResponse ? (
        <AgentLogViewer steps={logsResponse.steps} />
      ) : null}

      <DeletionLogsPanel />
    </section>
  );
}
