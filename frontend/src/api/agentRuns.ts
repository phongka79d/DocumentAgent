import axios from "axios";

import { apiClient } from "./client";
import type { AgentRunEvidence } from "../types/chat";
import type { AgentRunLogsResponse } from "../types/agentRuns";

export type AgentRunsApiErrorKind =
  | "backend"
  | "connection"
  | "request";

export type AgentRunsApiError = {
  kind: AgentRunsApiErrorKind;
  message: string;
  status?: number;
};

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the backend. Confirm the backend is running and try again.";

const GENERIC_REQUEST_ERROR_MESSAGE =
  "The agent run request failed. Please try again.";

type BackendErrorBody = {
  detail?: unknown;
};

export function getAgentRunsApiError(error: unknown): AgentRunsApiError {
  if (!axios.isAxiosError<BackendErrorBody>(error)) {
    return {
      kind: "request",
      message: GENERIC_REQUEST_ERROR_MESSAGE,
    };
  }

  const response = error.response;
  const detail = response?.data?.detail;

  if (response && typeof detail === "string" && detail.trim().length > 0) {
    return {
      kind: "backend",
      message: detail,
      status: response.status,
    };
  }

  if (error.request && !error.response) {
    return {
      kind: "connection",
      message: CONNECTION_ERROR_MESSAGE,
    };
  }

  if (response) {
    return {
      kind: "request",
      message: GENERIC_REQUEST_ERROR_MESSAGE,
      status: response.status,
    };
  }

  return {
    kind: "request",
    message: GENERIC_REQUEST_ERROR_MESSAGE,
  };
}

export function getAgentRunsApiErrorMessage(error: unknown): string {
  return getAgentRunsApiError(error).message;
}

export function getAgentRunEvidence(
  agentRunId: string,
): Promise<AgentRunEvidence> {
  const encodedAgentRunId = encodeURIComponent(agentRunId);

  return apiClient
    .get<AgentRunEvidence>(
      `/api/agent-runs/${encodedAgentRunId}/evidence`,
    )
    .then((response) => response.data);
}

export function getAgentRunLogs(
  agentRunId: string,
): Promise<AgentRunLogsResponse> {
  const encodedAgentRunId = encodeURIComponent(agentRunId);

  return apiClient
    .get<AgentRunLogsResponse>(
      `/api/agent-runs/${encodedAgentRunId}/logs`,
    )
    .then((response) => response.data);
}
