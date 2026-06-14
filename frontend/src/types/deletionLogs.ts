export type DeletionLogStatus = "success" | "failed";

export type DeletionLogCountKey =
  | "deleted_chunks"
  | "deleted_entities"
  | "deleted_relationships"
  | "deleted_agent_runs"
  | "deleted_agent_steps"
  | "deleted_chat_messages"
  | "deleted_chat_sessions";

export type DeletionLog = {
  id: string;
  document_id: string;
  file_name: string | null;
  status: DeletionLogStatus;
  failure_stage: string | null;
  error_message: string | null;
  deleted_storage_file: boolean;
  deleted_qdrant_points: boolean;
  deleted_chunks: number;
  deleted_entities: number;
  deleted_relationships: number;
  deleted_agent_runs: number;
  deleted_agent_steps: number;
  deleted_chat_messages: number;
  deleted_chat_sessions: number;
  created_at: string;
};

export type DeletionLogListResponse = {
  logs: DeletionLog[];
  limit: number;
  offset: number;
  has_more: boolean;
};
