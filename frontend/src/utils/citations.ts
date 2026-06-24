import type { SourceCitation } from "../api/types";

export interface CitationEntry {
  source: SourceCitation;
  index: number;
  label: string;
  bracketLabel: string;
  sourceKey: string;
}

export function normalizeCitationLabel(
  rawLabel: string | null | undefined,
  fallbackLabel: string,
): string {
  const cleaned = rawLabel?.trim().replace(/^\[/, "").replace(/\]$/, "");
  return cleaned || fallbackLabel;
}

export function getCitationLabel(
  source: SourceCitation,
  index: number,
): string {
  return normalizeCitationLabel(source.citation_key, `S${index + 1}`);
}

export function getBracketedCitationLabel(
  source: SourceCitation,
  index: number,
): string {
  return `[${getCitationLabel(source, index)}]`;
}

export function getSourceKey(source: SourceCitation): string {
  return `${source.document_id}:${source.chunk_id}:${source.chunk_index}`;
}

export function buildCitationEntries(
  sources: SourceCitation[],
): CitationEntry[] {
  return sources.map((source, index) => {
    const label = getCitationLabel(source, index);
    return {
      source,
      index,
      label,
      bracketLabel: `[${label}]`,
      sourceKey: getSourceKey(source),
    };
  });
}

export function findCitationEntryByLabel(
  entries: CitationEntry[],
  rawLabel: string,
): CitationEntry | null {
  const normalized = normalizeCitationLabel(rawLabel, rawLabel).toLowerCase();
  return (
    entries.find((entry) => entry.label.toLowerCase() === normalized) ?? null
  );
}

export function isSameSource(
  left: SourceCitation | null | undefined,
  right: SourceCitation | null | undefined,
): boolean {
  if (!left || !right) return false;
  return left.chunk_id === right.chunk_id && left.document_id === right.document_id;
}

export function formatPageRange(
  pageStart: number | null | undefined,
  pageEnd: number | null | undefined,
): string {
  if (pageStart === null || pageStart === undefined) {
    return "Chunk only";
  }

  if (pageEnd === null || pageEnd === undefined || pageEnd === pageStart) {
    return `Page ${pageStart}`;
  }

  return `Pages ${pageStart}-${pageEnd}`;
}

export function formatChunkLabel(source: SourceCitation): string {
  return `Chunk ${source.chunk_index}`;
}

export function formatSectionPath(
  sectionPath: string[] | null | undefined,
): string {
  if (!Array.isArray(sectionPath) || sectionPath.length === 0) {
    return "No section path";
  }

  return sectionPath.filter(Boolean).join(" / ") || "No section path";
}

export function formatScorePercent(
  score: number | null | undefined,
  digits = 0,
): string | null {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return null;
  }

  return `${(score * 100).toFixed(digits)}%`;
}

export function formatRawScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "N/A";
  }

  return score.toFixed(4);
}

export function getPrimaryScore(
  source: SourceCitation,
): number | null | undefined {
  return source.rerank_score ?? source.fusion_score ?? source.qdrant_score;
}

export function formatRetrievalPaths(
  paths: string[] | null | undefined,
): string {
  if (!Array.isArray(paths) || paths.length === 0) {
    return "Single path";
  }

  return paths.join(" + ");
}

export function getSourceTitle(source: SourceCitation): string {
  const pageRange = formatPageRange(source.page_start, source.page_end);
  return `${source.file_name} - ${pageRange}, ${formatChunkLabel(source)}`;
}
