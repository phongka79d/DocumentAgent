export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "ready"
  | "failed"
  | "deleting";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type DocumentChunk = {
  [key: string]: JsonValue;
};

export type DocumentListItem = {
  id: string;
  file_name: string;
  file_type: string;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  error_message?: string | null;
};

export type DocumentListResponse = {
  documents: DocumentListItem[];
};

export type DocumentUploadResponse = {
  document_id: string;
  file_name: string;
  status: DocumentStatus;
};

export type DocumentDetailResponse = DocumentListItem & {
  updated_at: string;
  chunks: DocumentChunk[];
};

export type DocumentDeleteResponse = {
  document_id: string;
  deleted: true;
  deleted_agent_runs: number;
  deleted_agent_steps: number;
  deleted_chat_messages: number;
  deleted_chat_sessions: number;
  deleted_chunks: number;
  deleted_entities: number;
  deleted_relationships: number;
  deleted_qdrant_points: boolean;
  deleted_storage_file: boolean;
};
