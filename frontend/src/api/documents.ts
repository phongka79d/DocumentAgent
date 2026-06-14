import axios, { type AxiosProgressEvent } from "axios";

import { apiClient } from "./client";
import type {
  DocumentDeleteResponse,
  DocumentDetailResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from "../types/documents";

export type DocumentApiErrorKind =
  | "backend"
  | "connection"
  | "request";

export type DocumentApiError = {
  kind: DocumentApiErrorKind;
  message: string;
};

export type DocumentUploadProgress = {
  loadedBytes: number;
  totalBytes: number | null;
  percent: number | null;
  isComputable: boolean;
};

const CONNECTION_ERROR_MESSAGE =
  "Unable to connect to the backend. Confirm the backend is running and try again.";

const GENERIC_REQUEST_ERROR_MESSAGE =
  "The document request failed. Please try again.";

type BackendErrorBody = {
  detail?: unknown;
};

export function getDocumentApiError(error: unknown): DocumentApiError {
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

export function getDocumentApiErrorMessage(error: unknown): string {
  return getDocumentApiError(error).message;
}

export function mapDocumentUploadProgress(
  progressEvent: AxiosProgressEvent,
): DocumentUploadProgress {
  const loadedBytes = Math.max(0, progressEvent.loaded);
  const totalBytes =
    typeof progressEvent.total === "number" && progressEvent.total > 0
      ? progressEvent.total
      : null;
  const percent =
    totalBytes === null
      ? null
      : Math.min(100, Math.round((loadedBytes / totalBytes) * 100));

  return {
    loadedBytes,
    totalBytes,
    percent,
    isComputable: totalBytes !== null,
  };
}

export function uploadDocument(
  file: File,
  onUploadProgress?: (progress: DocumentUploadProgress) => void,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient
    .post<DocumentUploadResponse>("/api/documents/upload", formData, {
      onUploadProgress: onUploadProgress
        ? (progressEvent) => {
            onUploadProgress(mapDocumentUploadProgress(progressEvent));
          }
        : undefined,
    })
    .then((response) => response.data);
}

export function listDocuments(): Promise<DocumentListResponse> {
  return apiClient
    .get<DocumentListResponse>("/api/documents")
    .then((response) => response.data);
}

export function getDocument(
  documentId: string,
): Promise<DocumentDetailResponse> {
  const encodedDocumentId = encodeURIComponent(documentId);

  return apiClient
    .get<DocumentDetailResponse>(`/api/documents/${encodedDocumentId}`)
    .then((response) => response.data);
}

export function deleteDocument(
  documentId: string,
): Promise<DocumentDeleteResponse> {
  const encodedDocumentId = encodeURIComponent(documentId);

  return apiClient
    .delete<DocumentDeleteResponse>(`/api/documents/${encodedDocumentId}`)
    .then((response) => response.data);
}
