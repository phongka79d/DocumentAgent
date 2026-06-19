import type {
  ChatRequest,
  ChatResponse,
  DocumentListResponse,
  DocumentProcessingResponse,
  DocumentResponse,
  UploadDocumentOptions,
  UploadDocumentResponse,
} from "./types";

export const DEFAULT_API_BASE_URL = "http://localhost:8000";
export const ADMIN_API_TOKEN_STORAGE_KEY = "ragdocument.admin-api-token";

export interface ApiClientConfig {
  baseUrl?: string;
  adminApiToken?: string | null;
  adminTokenStorageKey?: string;
  fetchImpl?: typeof fetch;
}

export interface ApiClient {
  uploadDocument(
    file: File,
    options?: UploadDocumentOptions,
  ): Promise<UploadDocumentResponse>;
  listDocuments(): Promise<DocumentListResponse>;
  getDocument(documentId: string): Promise<DocumentResponse>;
  indexDocument(documentId: string): Promise<DocumentProcessingResponse>;
  reindexDocument(documentId: string): Promise<DocumentProcessingResponse>;
  deleteDocument(documentId: string): Promise<DocumentResponse>;
  sendChatMessage(request: ChatRequest): Promise<ChatResponse>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function resolveApiBaseUrl(rawValue: string | undefined): string {
  const value = rawValue?.trim();
  if (!value) {
    return DEFAULT_API_BASE_URL;
  }

  return value.replace(/\/+$/, "");
}

function normalizeToken(value: string | null | undefined): string | null {
  const token = value?.trim();
  return token ? token : null;
}

function getSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function readBrowserAdminApiToken(
  storageKey: string = ADMIN_API_TOKEN_STORAGE_KEY,
): string | null {
  const storage = getSessionStorage();
  if (!storage) {
    return null;
  }

  try {
    return normalizeToken(storage.getItem(storageKey));
  } catch {
    return null;
  }
}

function writeBrowserAdminApiToken(
  token: string | null,
  storageKey: string = ADMIN_API_TOKEN_STORAGE_KEY,
): void {
  const storage = getSessionStorage();
  if (!storage) {
    return;
  }

  try {
    const normalizedToken = normalizeToken(token);
    if (normalizedToken) {
      storage.setItem(storageKey, normalizedToken);
    } else {
      storage.removeItem(storageKey);
    }
  } catch {
    return;
  }
}

function resolveFetchImpl(fetchImpl?: typeof fetch): typeof fetch {
  if (fetchImpl) {
    return fetchImpl;
  }

  const fallbackFetch = globalThis.fetch;
  if (typeof fallbackFetch === "function") {
    return fallbackFetch.bind(globalThis);
  }

  throw new Error("Fetch API is not available in this environment.");
}

function joinApiUrl(baseUrl: string, path: string): string {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBaseUrl}${normalizedPath}`;
}

function createHeaders(
  adminApiToken: string | null,
  headers?: HeadersInit,
): Headers {
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (adminApiToken) {
    requestHeaders.set("X-Admin-API-Token", adminApiToken);
  } else {
    requestHeaders.delete("X-Admin-API-Token");
  }
  return requestHeaders;
}

async function readResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    const text = await response.text();
    return text || null;
  } catch {
    return null;
  }
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (typeof body === "string") {
    const message = body.trim();
    if (message) {
      return message;
    }
  }

  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }

    if (Array.isArray(detail)) {
      const detailMessage = detail
        .map((entry) => {
          if (typeof entry === "string") {
            return entry.trim();
          }
          if (entry && typeof entry === "object") {
            const message = (entry as { msg?: unknown }).msg;
            if (typeof message === "string" && message.trim()) {
              return message.trim();
            }
          }
          return "";
        })
        .filter(Boolean)
        .join("; ");

      if (detailMessage) {
        return detailMessage;
      }
    }
  }

  return fallback;
}

async function createApiError(response: Response): Promise<ApiError> {
  const body = await readResponseBody(response);
  const fallbackMessage = response.statusText || "Request failed";
  return new ApiError(
    response.status,
    extractErrorMessage(body, fallbackMessage),
    body,
  );
}

function createRequestHandler(config: ApiClientConfig) {
  const runtimeEnv = import.meta as ImportMeta & {
    env?: {
      VITE_API_BASE_URL?: string;
    };
  };
  const baseUrl = resolveApiBaseUrl(
    config.baseUrl ?? runtimeEnv.env?.VITE_API_BASE_URL,
  );
  const adminTokenStorageKey =
    config.adminTokenStorageKey ?? ADMIN_API_TOKEN_STORAGE_KEY;

  const resolveAdminApiToken = () => {
    if (config.adminApiToken !== undefined) {
      return normalizeToken(config.adminApiToken);
    }

    return readBrowserAdminApiToken(adminTokenStorageKey);
  };

  async function request<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const fetchImpl = resolveFetchImpl(config.fetchImpl);
    const response = await fetchImpl(joinApiUrl(baseUrl, path), {
      ...init,
      headers: createHeaders(resolveAdminApiToken(), init.headers),
    });

    if (!response.ok) {
      throw await createApiError(response);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }

  return {
    uploadDocument(
      file: File,
      options: UploadDocumentOptions = {},
    ): Promise<UploadDocumentResponse> {
      const formData = new FormData();
      formData.append("file", file);

      const title = options.title?.trim();
      if (title) {
        formData.append("title", title);
      }

      return request<UploadDocumentResponse>("/api/documents/upload", {
        method: "POST",
        body: formData,
      });
    },

    listDocuments(): Promise<DocumentListResponse> {
      return request<DocumentListResponse>("/api/documents");
    },

    getDocument(documentId: string): Promise<DocumentResponse> {
      return request<DocumentResponse>(
        `/api/documents/${encodeURIComponent(documentId)}`,
      );
    },

    indexDocument(documentId: string): Promise<DocumentProcessingResponse> {
      return request<DocumentProcessingResponse>(
        `/api/documents/${encodeURIComponent(documentId)}/index`,
        {
          method: "POST",
        },
      );
    },

    reindexDocument(documentId: string): Promise<DocumentProcessingResponse> {
      return request<DocumentProcessingResponse>(
        `/api/documents/${encodeURIComponent(documentId)}/reindex`,
        {
          method: "POST",
        },
      );
    },

    deleteDocument(documentId: string): Promise<DocumentResponse> {
      return request<DocumentResponse>(
        `/api/documents/${encodeURIComponent(documentId)}`,
        {
          method: "DELETE",
        },
      );
    },

    sendChatMessage(requestBody: ChatRequest): Promise<ChatResponse> {
      return request<ChatResponse>("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });
    },
  } satisfies ApiClient;
}

export function createApiClient(config: ApiClientConfig = {}): ApiClient {
  return createRequestHandler(config);
}

export function getBrowserAdminApiToken(
  storageKey: string = ADMIN_API_TOKEN_STORAGE_KEY,
): string | null {
  return readBrowserAdminApiToken(storageKey);
}

export function setBrowserAdminApiToken(
  token: string | null,
  storageKey: string = ADMIN_API_TOKEN_STORAGE_KEY,
): void {
  writeBrowserAdminApiToken(token, storageKey);
}

export function clearBrowserAdminApiToken(
  storageKey: string = ADMIN_API_TOKEN_STORAGE_KEY,
): void {
  writeBrowserAdminApiToken(null, storageKey);
}

export const apiClient = createApiClient();

export function uploadDocument(
  file: File,
  options?: UploadDocumentOptions,
): Promise<UploadDocumentResponse> {
  return apiClient.uploadDocument(file, options);
}

export function listDocuments(): Promise<DocumentListResponse> {
  return apiClient.listDocuments();
}

export function getDocument(documentId: string): Promise<DocumentResponse> {
  return apiClient.getDocument(documentId);
}

export function indexDocument(
  documentId: string,
): Promise<DocumentProcessingResponse> {
  return apiClient.indexDocument(documentId);
}

export function reindexDocument(
  documentId: string,
): Promise<DocumentProcessingResponse> {
  return apiClient.reindexDocument(documentId);
}

export function deleteDocument(documentId: string): Promise<DocumentResponse> {
  return apiClient.deleteDocument(documentId);
}

export function sendChatMessage(requestBody: ChatRequest): Promise<ChatResponse> {
  return apiClient.sendChatMessage(requestBody);
}
