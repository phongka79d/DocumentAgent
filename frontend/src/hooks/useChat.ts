import { useCallback, useState } from "react";
import { apiClient } from "../api/client";
import type { ChatRequest, ChatResponse } from "../api/types";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

const MOCK_CHAT_RESPONSE: ChatResponse = {
  answer: "Hello! i'm DocuRAG, how can i help you today?",
  sources: [],
};

export interface UseChatReturn {
  question: string;
  activeQuestion: string;
  response: ChatResponse;
  isSubmitting: boolean;
  error: string | null;
  setQuestion: (value: string) => void;
  submit: (selectedDocumentIds: string[]) => Promise<void>;
  displayResponse: (response: ChatResponse, questionText: string) => void;
  reset: () => void;
}

export function useChat(): UseChatReturn {
  const [question, setQuestionState] = useState("");
  const [activeQuestion, setActiveQuestion] = useState("");
  const [responseState, setResponseState] = useState<ChatResponse>(MOCK_CHAT_RESPONSE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setQuestion = useCallback((value: string) => {
    setQuestionState(value);
    setError(null);
  }, []);

  const displayResponse = useCallback(
    (newResponse: ChatResponse, questionText: string) => {
      setResponseState(newResponse);
      setActiveQuestion(questionText);
      setQuestionState("");
      setError(null);
    },
    [],
  );

  const submit = useCallback(
    async (selectedDocumentIds: string[]) => {
      const trimmed = question.trim();
      if (!trimmed || isSubmitting) return;

      setIsSubmitting(true);
      setError(null);
      setActiveQuestion(trimmed);

      try {
        const request: ChatRequest = { question: trimmed, save_message: true };
        if (selectedDocumentIds.length > 0) {
          request.document_ids = selectedDocumentIds;
        }
        const chatResponse = await apiClient.sendChatMessage(request);
        setResponseState(chatResponse);
        setQuestionState("");
      } catch (err) {
        setError(getErrorMessage(err, "Unable to send question."));
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, question],
  );

  const reset = useCallback(() => {
    setQuestionState("");
    setActiveQuestion("");
    setResponseState(MOCK_CHAT_RESPONSE);
    setError(null);
  }, []);

  return {
    question,
    activeQuestion,
    response: responseState,
    isSubmitting,
    error,
    setQuestion,
    submit,
    displayResponse,
    reset,
  };
}
