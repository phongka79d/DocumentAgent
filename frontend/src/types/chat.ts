export type AskQuestionRequest = {
  session_id?: string | null;
  question: string;
  document_ids: string[];
};

export type ChatCitation = {
  file_name: string;
  quote: string;
};

export type AskQuestionResponse = {
  answer: string;
  confidence: number | null;
  citations: ChatCitation[];
  agent_run_id: string;
};

export type VerifiedEvidenceChunk = {
  chunk_id?: string;
  document_id?: string;
  file_name: string;
  quote: string;
  page_number?: number | null;
  verification_reason?: string;
  supports_simple_reasoning?: boolean;
};

export type RejectedEvidenceChunk = {
  chunk_id?: string;
  document_id?: string;
  file_name: string;
  quote: string;
  rejection_reason: string;
};

export type AgentRunEvidence = {
  verified_chunks: VerifiedEvidenceChunk[];
  rejected_chunks: RejectedEvidenceChunk[];
};
