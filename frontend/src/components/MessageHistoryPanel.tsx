import type { MessageHistoryItem } from "../api/types";

interface MessageHistoryPanelProps {
  messages: MessageHistoryItem[];
  selectedMessageId: string | null;
  isLoading: boolean;
  hasLoaded: boolean;
  error: string | null;
  onRefresh: () => Promise<void>;
  onSelectMessage: (message: MessageHistoryItem) => void;
}

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function formatCreatedAt(value: string | null): string {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }
  return DATE_TIME_FORMATTER.format(date);
}

function getAnswerPreview(answer: string): string {
  const preview = answer.replace(/\s+/g, " ").trim();
  if (!preview) {
    return "No saved answer";
  }
  return preview;
}

function getSourceCountLabel(count: number): string {
  return count === 1 ? "1 source" : `${count} sources`;
}

export default function MessageHistoryPanel({
  messages,
  selectedMessageId,
  hasLoaded,
  error,
  onSelectMessage,
}: MessageHistoryPanelProps) {
  if (error) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon" style={{ color: "var(--danger)" }}>error</span>
        <h3 className="state-title" style={{ color: "var(--danger)" }}>Error Loading History</h3>
        <p className="state-message">{error}</p>
      </div>
    );
  }

  if (!hasLoaded) {
    return (
      <div className="state-container">
        <span className="spinner state-icon" aria-hidden="true" />
        <h3 className="state-title">Loading History</h3>
        <p className="state-message">Fetching message history from the server...</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="state-container">
        <span className="material-symbols-outlined state-icon">history</span>
        <h3 className="state-title">No History Yet</h3>
        <p className="state-message">Your conversation history will appear here once you start asking questions.</p>
      </div>
    );
  }

  return (
    <div className="history-grid">
      {messages.map((message) => {
        const sourceCount = Array.isArray(message.sources)
          ? message.sources.length
          : 0;
        const isSelected = message.id === selectedMessageId;

        return (
          <button
            key={message.id}
            className={`history-card ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectMessage(message)}
            aria-pressed={isSelected}
          >
            <div className="history-card-header">
              <span className="history-card-time">{formatCreatedAt(message.created_at)}</span>
              <span className="history-card-sources">{getSourceCountLabel(sourceCount)}</span>
            </div>
            <div className="history-card-question">{message.question}</div>
            <div className="history-card-answer">
              {getAnswerPreview(message.answer)}
            </div>
          </button>
        );
      })}
    </div>
  );
}

