import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { DocumentChunk, SourceCitation } from "../api/types";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

type ChunkLoadStatus = "idle" | "loading" | "ready" | "error";

interface ChunkLoadState {
  status: ChunkLoadStatus;
  error: string | null;
}

const INITIAL_CHUNK_LOAD_STATE: ChunkLoadState = {
  status: "idle",
  error: null,
};

export interface UseChunksReturn {
  selectedSource: SourceCitation | null;
  selectedChunkIndex: number | null;
  selectedChunk: DocumentChunk | null;
  previousChunk: DocumentChunk | null;
  nextChunk: DocumentChunk | null;
  hasPreviousChunk: boolean;
  hasNextChunk: boolean;
  isLoading: boolean;
  error: string | null;
  selectSource: (source: SourceCitation) => void;
  viewPreviousChunk: () => void;
  viewNextChunk: () => void;
  clearSelection: () => void;
}

export function useChunks(): UseChunksReturn {
  const [cache, setCache] = useState<Record<string, DocumentChunk[]>>({});
  const [loadStates, setLoadStates] = useState<Record<string, ChunkLoadState>>({});
  const [selectedSource, setSelectedSource] = useState<SourceCitation | null>(null);
  const [selectedChunkIndex, setSelectedChunkIndex] = useState<number | null>(null);

  const loadState = selectedSource
    ? loadStates[selectedSource.document_id] ?? INITIAL_CHUNK_LOAD_STATE
    : INITIAL_CHUNK_LOAD_STATE;

  const documentChunks = selectedSource
    ? cache[selectedSource.document_id] ?? null
    : null;

  const selectedChunk = useMemo(() => {
    if (!documentChunks || selectedChunkIndex === null) return null;
    return documentChunks.find((c) => c.chunk_index === selectedChunkIndex) ?? null;
  }, [documentChunks, selectedChunkIndex]);

  const previousChunk = useMemo(() => {
    if (!selectedChunk || !documentChunks) return null;
    return documentChunks.find((c) => c.chunk_index === selectedChunk.chunk_index - 1) ?? null;
  }, [selectedChunk, documentChunks]);

  const nextChunk = useMemo(() => {
    if (!selectedChunk || !documentChunks) return null;
    return documentChunks.find((c) => c.chunk_index === selectedChunk.chunk_index + 1) ?? null;
  }, [selectedChunk, documentChunks]);

  const loadDocumentChunks = useCallback(async (documentId: string) => {
    setLoadStates((prev) => ({
      ...prev,
      [documentId]: { status: "loading", error: null },
    }));
    try {
      const response = await apiClient.getDocumentChunks(documentId);
      setCache((prev) => ({
        ...prev,
        [documentId]: Array.isArray(response.chunks) ? response.chunks : [],
      }));
      setLoadStates((prev) => ({
        ...prev,
        [documentId]: { status: "ready", error: null },
      }));
    } catch (err) {
      setLoadStates((prev) => ({
        ...prev,
        [documentId]: {
          status: "error",
          error: getErrorMessage(err, "Unable to load source."),
        },
      }));
    }
  }, []);

  const selectSource = useCallback((source: SourceCitation) => {
    setSelectedSource({ ...source });
    setSelectedChunkIndex(source.chunk_index);
    setLoadStates((prev) => {
      const existing = prev[source.document_id];
      if (!existing || existing.status !== "error") return prev;
      return { ...prev, [source.document_id]: INITIAL_CHUNK_LOAD_STATE };
    });
  }, []);

  const viewPreviousChunk = useCallback(() => {
    if (!previousChunk) return;
    setSelectedChunkIndex(previousChunk.chunk_index);
  }, [previousChunk]);

  const viewNextChunk = useCallback(() => {
    if (!nextChunk) return;
    setSelectedChunkIndex(nextChunk.chunk_index);
  }, [nextChunk]);

  const clearSelection = useCallback(() => {
    setSelectedSource(null);
    setSelectedChunkIndex(null);
  }, []);

  // Trigger chunk load when a new source is selected
  useEffect(() => {
    if (!selectedSource) return;
    const docId = selectedSource.document_id;
    const state = loadStates[docId] ?? INITIAL_CHUNK_LOAD_STATE;
    if (state.status === "idle") {
      void loadDocumentChunks(docId);
    }
  }, [loadStates, loadDocumentChunks, selectedSource]);

  return {
    selectedSource,
    selectedChunkIndex,
    selectedChunk,
    previousChunk,
    nextChunk,
    hasPreviousChunk: previousChunk !== null,
    hasNextChunk: nextChunk !== null,
    isLoading: loadState.status === "loading",
    error: loadState.status === "error" ? loadState.error : null,
    selectSource,
    viewPreviousChunk,
    viewNextChunk,
    clearSelection,
  };
}
