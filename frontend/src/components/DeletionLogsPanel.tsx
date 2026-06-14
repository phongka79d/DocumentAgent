import { useEffect, useRef, useState } from "react";

import {
  getDeletionLogsApiErrorMessage,
  listDeletionLogs,
} from "../api/deletionLogs";
import type {
  DeletionLog,
  DeletionLogCountKey,
  DeletionLogStatus,
} from "../types/deletionLogs";

type Filter = "all" | DeletionLogStatus;
type LoadState = "idle" | "loading" | "success" | "error";

const PAGE_SIZE = 20;

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "success", label: "Successful" },
  { value: "failed", label: "Failed" },
];

const COUNT_FIELDS: Array<{ key: DeletionLogCountKey; label: string }> = [
  { key: "deleted_chunks", label: "Chunks" },
  { key: "deleted_entities", label: "Entities" },
  { key: "deleted_relationships", label: "Relationships" },
  { key: "deleted_agent_runs", label: "Agent runs" },
  { key: "deleted_agent_steps", label: "Agent steps" },
  { key: "deleted_chat_messages", label: "Chat messages" },
  { key: "deleted_chat_sessions", label: "Chat sessions" },
];

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(date);
}

function displayFileName(log: DeletionLog): string {
  return log.file_name?.trim() || "Deleted document";
}

export function DeletionLogsPanel() {
  const [filter, setFilter] = useState<Filter>("all");
  const [offset, setOffset] = useState(0);
  const [logs, setLogs] = useState<DeletionLog[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(
    () => new Set(),
  );
  const latestRequestIdRef = useRef(0);

  useEffect(() => {
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    setLoadState("loading");
    setErrorMessage(null);
    setLogs([]);
    setHasMore(false);

    listDeletionLogs({
      status: filter === "all" ? null : filter,
      limit: PAGE_SIZE,
      offset,
    })
      .then((response) => {
        if (latestRequestIdRef.current !== requestId) {
          return;
        }

        setLogs(response.logs);
        setHasMore(response.has_more);
        setLoadState("success");
      })
      .catch((error: unknown) => {
        if (latestRequestIdRef.current !== requestId) {
          return;
        }

        setLogs([]);
        setHasMore(false);
        setErrorMessage(getDeletionLogsApiErrorMessage(error));
        setLoadState("error");
      });
  }, [filter, offset]);

  function handleFilterChange(nextFilter: Filter) {
    if (nextFilter === filter) {
      return;
    }

    setFilter(nextFilter);
    setOffset(0);
    setExpandedLogIds(new Set());
  }

  function handleDetailsToggle(logId: string, isOpen: boolean) {
    setExpandedLogIds((current) => {
      const next = new Set(current);

      if (isOpen) {
        next.add(logId);
      } else {
        next.delete(logId);
      }

      return next;
    });
  }

  const isLoading = loadState === "loading";
  const canGoPrevious = offset > 0 && !isLoading;
  const canGoNext = hasMore && !isLoading;

  return (
    <section
      className="deletion-logs-panel"
      aria-labelledby="deletion-logs-title"
    >
      <header className="deletion-logs-panel__header">
        <div>
          <p className="deletion-logs-panel__eyebrow">Deletion audit</p>
          <h2 id="deletion-logs-title">Deletion Logs</h2>
        </div>
        <p>
          Persistent audit records for successful and failed document deletion
          attempts.
        </p>
      </header>

      <div
        className="deletion-logs-panel__filters"
        aria-label="Deletion log filters"
        role="group"
      >
        {FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            className={
              item.value === filter
                ? "deletion-logs-panel__filter deletion-logs-panel__filter--active"
                : "deletion-logs-panel__filter"
            }
            aria-pressed={item.value === filter}
            disabled={isLoading}
            onClick={() => handleFilterChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="deletion-logs-panel__message" role="status">
          Loading deletion logs...
        </p>
      ) : null}

      {loadState === "error" ? (
        <p className="deletion-logs-panel__error" role="alert">
          {errorMessage ??
            "Unable to load deletion logs. Confirm the backend is running and try again."}
        </p>
      ) : null}

      {loadState === "success" && logs.length === 0 ? (
        <p className="deletion-logs-panel__message" role="status">
          No deletion logs found for this filter.
        </p>
      ) : null}

      {logs.length > 0 ? (
        <ol className="deletion-logs-panel__list">
          {logs.map((log) => (
            <li key={log.id} className="deletion-logs-panel__item">
              <details
                className="deletion-logs-panel__details"
                open={expandedLogIds.has(log.id)}
                onToggle={(event) =>
                  handleDetailsToggle(log.id, event.currentTarget.open)
                }
              >
                <summary className="deletion-logs-panel__summary">
                  <span className="deletion-logs-panel__summary-main">
                    <span className="deletion-logs-panel__file-name">
                      {displayFileName(log)}
                    </span>
                    <span className="deletion-logs-panel__document-id">
                      {log.document_id}
                    </span>
                  </span>
                  <span className="deletion-logs-panel__summary-meta">
                    <time dateTime={log.created_at}>
                      {formatTimestamp(log.created_at)}
                    </time>
                    <span
                      className={`deletion-logs-panel__status deletion-logs-panel__status--${log.status}`}
                    >
                      {log.status === "success" ? "Success" : "Failed"}
                    </span>
                  </span>
                </summary>

                <div className="deletion-logs-panel__expanded">
                  <dl className="deletion-logs-panel__facts">
                    <div>
                      <dt>Document ID</dt>
                      <dd>{log.document_id}</dd>
                    </div>
                    <div>
                      <dt>Storage file</dt>
                      <dd>{log.deleted_storage_file ? "Deleted" : "Not deleted"}</dd>
                    </div>
                    <div>
                      <dt>Qdrant points</dt>
                      <dd>
                        {log.deleted_qdrant_points ? "Deleted" : "Not deleted"}
                      </dd>
                    </div>
                    {log.status === "failed" ? (
                      <>
                        <div>
                          <dt>Failure stage</dt>
                          <dd>{log.failure_stage ?? "Unknown"}</dd>
                        </div>
                        <div>
                          <dt>Error</dt>
                          <dd>
                            {log.error_message ??
                              "Document deletion failed. Please try again."}
                          </dd>
                        </div>
                      </>
                    ) : null}
                  </dl>

                  <dl className="deletion-logs-panel__counts">
                    {COUNT_FIELDS.map((field) => (
                      <div key={field.key}>
                        <dt>{field.label}</dt>
                        <dd>{String(log[field.key])}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </details>
            </li>
          ))}
        </ol>
      ) : null}

      <nav className="deletion-logs-panel__pagination" aria-label="Deletion log pagination">
        <button
          type="button"
          disabled={!canGoPrevious}
          onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
        >
          Previous
        </button>
        <span>
          {logs.length > 0
            ? `Showing ${offset + 1}-${offset + logs.length}`
            : "Showing 0"}
        </span>
        <button
          type="button"
          disabled={!canGoNext}
          onClick={() => setOffset((current) => current + PAGE_SIZE)}
        >
          Next
        </button>
      </nav>
    </section>
  );
}
