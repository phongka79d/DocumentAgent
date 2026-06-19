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
  isLoading,
  hasLoaded,
  error,
  onRefresh,
  onSelectMessage,
}: MessageHistoryPanelProps) {
  const isRefreshing = hasLoaded && isLoading;

  return (
    <section className="panel" aria-label="Message history">
      <div className="panel-heading">
        <h2>Message history</h2>
        <button
          className="button button--secondary button--compact"
          type="button"
          onClick={() => void onRefresh()}
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isRefreshing ? (
            <span className="button-spinner" aria-hidden="true" />
          ) : null}
          <span>{isRefreshing ? "Refreshing" : "Refresh"}</span>
        </button>
      </div>

      {error ? <div className="message-history-state message-history-state--error">{error}</div> : null}

      {!error && !hasLoaded ? (
        <div className="message-history-state">Loading history</div>
      ) : null}

      {!error && hasLoaded && messages.length === 0 ? (
        <div className="message-history-state">No saved messages yet</div>
      ) : null}

      {!error && messages.length > 0 ? (
        <ol className="message-history-list">
          {messages.map((message) => {
            const sourceCount = Array.isArray(message.sources)
              ? message.sources.length
              : 0;
            const isSelected = message.id === selectedMessageId;

            return (
              <li key={message.id} className="message-history-list__item">
                <button
                  className={`message-history-card${
                    isSelected ? " message-history-card--selected" : ""
                  }`}
                  type="button"
                  onClick={() => onSelectMessage(message)}
                  aria-pressed={isSelected}
                >
                  <div className="message-history-card__meta">
                    <span>{formatCreatedAt(message.created_at)}</span>
                    <span>{getSourceCountLabel(sourceCount)}</span>
                  </div>
                  <div className="message-history-card__question">{message.question}</div>
                  <div className="message-history-card__answer">
                    {getAnswerPreview(message.answer)}
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      ) : null}
    </section>
  );
}
