export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface DocumentResponse {
  id: string;
  title: string | null;
  file_name: string;
  mime_type: string | null;
  file_size: number | null;
  file_hash: string | null;
  storage_path: string;
  status: DocumentStatus;
  total_pages: number | null;
  total_chunks: number;
  parser_name: string | null;
  parser_version: string | null;
  chunking_strategy: string | null;
  chunking_version: string | null;
  embedding_model: string | null;
  embedding_dimension: number | null;
  qdrant_collection: string | null;
  indexed_at: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  content_hash: string | null;
  token_count: number | null;
  chunk_type: string | null;
  heading: string | null;
  section_path: string[];
  page_start: number | null;
  page_end: number | null;
  token_start: number | null;
  token_end: number | null;
  qdrant_point_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

export interface DocumentChunkListResponse {
  document_id: string;
  chunks: DocumentChunk[];
}

export interface UploadDocumentResponse {
  document_id: string;
  status: DocumentStatus;
  duplicate: boolean;
}

export interface DocumentProcessingResponse {
  document_id: string;
  status: "processing";
}

export interface ChatRequest {
  question: string;
  document_ids?: string[];
  save_message?: boolean;
}


export interface SourceCitation {
  document_id: string;
  chunk_id: string;
  file_name: string;
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  heading: string | null;
  qdrant_score: number | null;
  rerank_score: number | null;
  section_path?: string[];
  content_preview?: string;
  is_neighbor_context?: boolean;
  fusion_score?: number | null;
  retrieval_paths?: string[] | null;
  citation_key?: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: SourceCitation[];
}

export interface MessageHistoryItem {
  id: string;
  question: string;
  answer: string;
  sources: SourceCitation[];
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface MessageListResponse {
  messages: MessageHistoryItem[];
}

export interface UploadDocumentOptions {
  title?: string;
}
