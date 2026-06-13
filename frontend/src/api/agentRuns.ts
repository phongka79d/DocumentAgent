import axios from "axios";

import { apiClient } from "./client";
import type { AgentRunEvidence } from "../types/chat";

export type AgentRunsApiErrorKind =
  | "backend"
  | "connection"
  | "request";

export type AgentRunsApiError = {
  kind: AgentRunsApiErrorKind;
  message: string;
};

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the backend. Confirm the backend is running and try again.";

const GENERIC_REQUEST_ERROR_MESSAGE =
  "The evidence request failed. Please try again.";

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

  const detail = error.response?.data?.detail;

  if (typeof detail === "string" && detail.trim().length > 0) {
    return {
      kind: "backend",
      message: detail,
    };
  }

  if (error.request && !error.response) {
    return {
      kind: "connection",
      message: CONNECTION_ERROR_MESSAGE,
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
