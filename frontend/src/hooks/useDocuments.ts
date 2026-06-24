import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  DocumentAction,
  DocumentResponse,
} from "../api/types";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

export interface UseDocumentsReturn {
  documents: DocumentResponse[];
  filteredDocuments: DocumentResponse[];
  readyDocuments: DocumentResponse[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  isUploading: boolean;
  uploadError: string | null;
  uploadResult: string | null;
  pendingAction: { documentId: string; kind: DocumentAction } | null;
  isBusy: boolean;
  selectedDocumentIds: string[];
  selectedReadyDocumentIds: string[];
  loadDocuments: (options?: { background?: boolean }) => Promise<void>;
  uploadDocument: (file: File) => Promise<void>;
  handleDocumentAction: (documentId: string, kind: DocumentAction) => Promise<void>;
  toggleSelectedDocument: (documentId: string) => void;
  refreshDocuments: () => Promise<void>;
  searchTerm: string;
  setSearchTerm: (term: string) => void;
}

export function useDocuments(): UseDocumentsReturn {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{
    documentId: string;
    kind: DocumentAction;
  } | null>(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  const readyDocuments = useMemo(
    () => documents.filter((d) => d.status === "ready"),
    [documents],
  );

  const selectedReadyDocumentIds = useMemo(() => {
    if (selectedDocumentIds.length === 0 || readyDocuments.length === 0) return [];
    const readySet = new Set(readyDocuments.map((d) => d.id));
    return selectedDocumentIds.filter((id) => readySet.has(id));
  }, [readyDocuments, selectedDocumentIds]);

  const filteredDocuments = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return documents;
    return documents.filter((d) => d.file_name.toLowerCase().includes(term));
  }, [documents, searchTerm]);

  const isBusy = isUploading || pendingAction !== null;

  const loadDocuments = useCallback(
    async (options: { background?: boolean } = {}) => {
      const { background = false } = options;
      if (background) setIsRefreshing(true);
      else setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.listDocuments();
        setDocuments(Array.isArray(response.documents) ? response.documents : []);
      } catch (err) {
        setError(getErrorMessage(err, "Unable to load documents."));
      } finally {
        if (background) setIsRefreshing(false);
        else setIsLoading(false);
      }
    },
    [],
  );

  const uploadDocument = useCallback(
    async (file: File) => {
      if (isBusy) return;
      setIsUploading(true);
      setUploadError(null);
      setUploadResult(null);
      try {
        const response = await apiClient.uploadDocument(file);
        setUploadResult(response.duplicate ? "Duplicate upload" : "Uploaded");
        await loadDocuments({ background: true });
      } catch (err) {
        setUploadError(getErrorMessage(err, "Unable to upload document."));
      } finally {
        setIsUploading(false);
      }
    },
    [isBusy, loadDocuments],
  );

  const handleDocumentAction = useCallback(
    async (documentId: string, kind: DocumentAction) => {
      if (isBusy) return;
      setPendingAction({ documentId, kind });
      setError(null);
      try {
        if (kind === "index") {
          await apiClient.indexDocument(documentId);
        } else if (kind === "reindex") {
          await apiClient.reindexDocument(documentId);
        } else {
          await apiClient.deleteDocument(documentId);
          setDocuments((prev) => prev.filter((d) => d.id !== documentId));
        }
        await loadDocuments({ background: true });
      } catch (err) {
        setError(
          getErrorMessage(
            err,
            `Unable to ${kind === "reindex" ? "re-index" : kind} document.`,
          ),
        );
      } finally {
        setPendingAction(null);
      }
    },
    [isBusy, loadDocuments],
  );

  const toggleSelectedDocument = useCallback((documentId: string) => {
    setSelectedDocumentIds((prev) =>
      prev.includes(documentId)
        ? prev.filter((id) => id !== documentId)
        : [...prev, documentId],
    );
  }, []);

  const refreshDocuments = useCallback(async () => {
    await loadDocuments({ background: true });
  }, [loadDocuments]);

  // Remove stale selected doc IDs when documents load
  useEffect(() => {
    if (selectedDocumentIds.length === 0) return;
    const readySet = new Set(readyDocuments.map((d) => d.id));
    const nextIds = selectedDocumentIds.filter((id) => readySet.has(id));
    if (nextIds.length !== selectedDocumentIds.length) {
      setSelectedDocumentIds(nextIds);
    }
  }, [readyDocuments, selectedDocumentIds]);

  // Load on mount
  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  return {
    documents,
    filteredDocuments,
    readyDocuments,
    isLoading,
    isRefreshing,
    error,
    isUploading,
    uploadError,
    uploadResult,
    pendingAction,
    isBusy,
    selectedDocumentIds,
    selectedReadyDocumentIds,
    loadDocuments,
    uploadDocument,
    handleDocumentAction,
    toggleSelectedDocument,
    refreshDocuments,
    searchTerm,
    setSearchTerm,
  };
}
