import type { SourceCitation } from "../api/types";
import {
  formatRawScore,
  formatRetrievalPaths,
  formatScorePercent,
} from "../utils/citations";

interface RetrievalMetricsProps {
  source: SourceCitation;
  compact?: boolean;
}

interface ScoreBadgeProps {
  label: string;
  value: number | null | undefined;
  compact: boolean;
}

function ScoreBadge({ label, value, compact }: ScoreBadgeProps) {
  const percent = formatScorePercent(value);
  if (!percent) {
    return null;
  }

  const clamped = Math.max(0, Math.min(100, value * 100));

  return (
    <span className="metric-badge metric-badge-score" title={`${label}: ${formatRawScore(value)}`}>
      <span className="metric-badge-label">{label}</span>
      <span className="metric-badge-value">{compact ? percent : formatRawScore(value)}</span>
      {!compact ? (
        <span className="metric-score-bar" aria-hidden="true">
          <span style={{ width: `${clamped}%` }} />
        </span>
      ) : null}
    </span>
  );
}

export default function RetrievalMetrics({
  source,
  compact = false,
}: RetrievalMetricsProps) {
  const retrievalPaths = source.retrieval_paths ?? [];

  return (
    <div className={`retrieval-metrics ${compact ? "compact" : ""}`}>
      <ScoreBadge label="Semantic" value={source.qdrant_score} compact={compact} />
      <ScoreBadge label="Rerank" value={source.rerank_score} compact={compact} />
      <ScoreBadge label="Fusion" value={source.fusion_score} compact={compact} />

      {retrievalPaths.length > 0 ? (
        <span
          className="metric-badge metric-badge-path"
          title={`Retrieval paths: ${formatRetrievalPaths(retrievalPaths)}`}
        >
          <span className="material-symbols-outlined" aria-hidden="true">account_tree</span>
          <span>{compact ? `${retrievalPaths.length} path` : formatRetrievalPaths(retrievalPaths)}</span>
        </span>
      ) : null}

      {source.is_neighbor_context ? (
        <span className="metric-badge metric-badge-context" title="Adjacent context chunk">
          <span className="material-symbols-outlined" aria-hidden="true">join_inner</span>
          <span>Context</span>
        </span>
      ) : null}
    </div>
  );
}
