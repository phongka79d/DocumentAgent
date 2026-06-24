import { useCallback, useState } from "react";
import { apiClient } from "../api/client";
import type { MessageHistoryItem } from "../api/types";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

const MESSAGE_HISTORY_LIMIT = 25;

export interface UseMessageHistoryReturn {
  messages: MessageHistoryItem[];
  isLoading: boolean;
  hasLoaded: boolean;
  error: string | null;
  selectedMessageId: string | null;
  load: () => Promise<void>;
  refresh: () => Promise<void>;
  selectMessage: (message: MessageHistoryItem) => void;
}

export function useMessageHistory(): UseMessageHistoryReturn {
  const [messages, setMessages] = useState<MessageHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.listMessages(MESSAGE_HISTORY_LIMIT);
      const next = Array.isArray(response.messages) ? response.messages : [];
      setMessages(next);
      setSelectedMessageId((curr) =>
        next.some((m) => m.id === curr) ? curr : null,
      );
    } catch (err) {
      setError(getErrorMessage(err, "Unable to load message history."));
    } finally {
      setHasLoaded(true);
      setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  const selectMessage = useCallback((message: MessageHistoryItem) => {
    setSelectedMessageId(message.id);
  }, []);

  return {
    messages,
    isLoading,
    hasLoaded,
    error,
    selectedMessageId,
    load,
    refresh,
    selectMessage,
  };
}
