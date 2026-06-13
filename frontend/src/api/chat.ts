import axios from "axios";

import { apiClient } from "./client";
import type {
  AskQuestionRequest,
  AskQuestionResponse,
} from "../types/chat";

export type ChatApiErrorKind =
  | "backend"
  | "connection"
  | "request";

export type ChatApiError = {
  kind: ChatApiErrorKind;
  message: string;
};

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the backend. Confirm the backend is running and try again.";

const GENERIC_REQUEST_ERROR_MESSAGE =
  "The chat request failed. Please try again.";

type BackendErrorBody = {
  detail?: unknown;
};

export function getChatApiError(error: unknown): ChatApiError {
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

export function getChatApiErrorMessage(error: unknown): string {
  return getChatApiError(error).message;
}

export function askQuestion(
  request: AskQuestionRequest,
): Promise<AskQuestionResponse> {
  return apiClient
    .post<AskQuestionResponse>("/api/chat/ask", request)
    .then((response) => response.data);
}
