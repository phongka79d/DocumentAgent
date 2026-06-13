export const AGENT_STEP_NAMES = {
  retrieval: "agent_1_retrieval",
  verification: "agent_2_verification",
  answerSelfCheck: "agent_3_answer_self_check",
} as const;

export type RecognizedAgentStepName =
  (typeof AGENT_STEP_NAMES)[keyof typeof AGENT_STEP_NAMES];

export type AgentStepName =
  | RecognizedAgentStepName
  | (string & Record<never, never>);

export type AgentStepStatus = "success" | "failed";

export type AgentStep = {
  agent_name: string;
  step_name: AgentStepName;
  input: unknown;
  output: unknown;
  status: AgentStepStatus;
  created_at: string;
  error_message: string | null;
};

export type AgentRunLogsResponse = {
  agent_run_id: string;
  steps: AgentStep[];
};
