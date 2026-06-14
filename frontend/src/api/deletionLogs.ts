import axios from "axios";

import { apiClient } from "./client";
import type {
  DeletionLogListResponse,
  DeletionLogStatus,
} from "../types/deletionLogs";

export type DeletionLogsApiErrorKind =
  | "backend"
  | "connection"
  | "request";

export type DeletionLogsApiError = {
  kind: DeletionLogsApiErrorKind;
  message: string;
  status?: number;
};

export type ListDeletionLogsParams = {
  status?: DeletionLogStatus | null;
  limit: number;
  offset: number;
};

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the backend. Confirm the backend is running and try again.";

const GENERIC_REQUEST_ERROR_MESSAGE =
  "The deletion logs request failed. Please try again.";

type BackendErrorBody = {
  detail?: unknown;
};

export function getDeletionLogsApiError(
  error: unknown,
): DeletionLogsApiError {
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

export function getDeletionLogsApiErrorMessage(error: unknown): string {
  return getDeletionLogsApiError(error).message;
}

export function listDeletionLogs({
  status,
  limit,
  offset,
}: ListDeletionLogsParams): Promise<DeletionLogListResponse> {
  const params: {
    status?: DeletionLogStatus;
    limit: number;
    offset: number;
  } = {
    limit,
    offset,
  };

  if (status) {
    params.status = status;
  }

  return apiClient
    .get<DeletionLogListResponse>("/api/deletion-logs", { params })
    .then((response) => response.data);
}
