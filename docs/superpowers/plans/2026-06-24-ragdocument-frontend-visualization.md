# RagDocument Frontend Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the RagDocument frontend with interactive citations, a references drawer, retrieval metric visibility, and modern centralized styling without changing the chat API contract.

**Architecture:** Keep `useChat`, `apiClient.sendChatMessage`, and existing response/history state ownership unchanged. Add small presentation-focused components that consume the existing `SourceCitation` fields and delegate chunk loading to the existing `useChunks` selection and adjacent chunk navigation flow.

**Tech Stack:** React 18, TypeScript, Vite, CSS in `frontend/src/styles.css`, existing Material Symbols icon font.

---

## File Structure

- Create `frontend/src/utils/citations.ts`: Pure citation formatting, lookup, score, page range, and source identity helpers.
- Create `frontend/src/components/RetrievalMetrics.tsx`: Reusable score/path/status badge visualization for source cards, popovers, and drawer metadata.
- Create `frontend/src/components/CitationText.tsx`: Parses answer text and renders clickable `[S1]`-style citation pills with accessible preview popovers.
- Create `frontend/src/components/ReferencesDrawer.tsx`: Owns the right drawer presentation, source navigator, active source summary, and existing chunk preview panel.
- Modify `frontend/src/components/ChatPanel.tsx`: Replace raw answer text with `CitationText` and keep `onSelectSource` unchanged.
- Modify `frontend/src/components/SourceList.tsx`: Rework source cards into compact reference cards using shared helpers and metrics.
- Modify `frontend/src/components/ChunkViewerPanel.tsx`: Improve metadata and metric display while preserving previous/next chunk callbacks.
- Modify `frontend/src/App.tsx`: Replace inline preview drawer markup with `ReferencesDrawer`.
- Modify `frontend/src/styles.css`: Centralize all new citation, drawer, metric, glass, dark-mode, motion, and responsive styling.

## Safety Rules

- Do not modify `frontend/src/hooks/useChat.ts`.
- Do not modify `frontend/src/api/client.ts`.
- Do not modify the exported `SourceCitation` or `ChatResponse` public interfaces in `frontend/src/api/types.ts`.
- Do not introduce mock credentials, new API base URLs, or fake retrieval values.
- Use existing `SourceCitation` fields only: `citation_key`, `content_preview`, `section_path`, `page_start`, `page_end`, `qdrant_score`, `rerank_score`, `fusion_score`, `retrieval_paths`, and `is_neighbor_context`.
- Keep styling centralized in `frontend/src/styles.css`; remove touched inline visual styles when practical.
- Verify each phase with `npm run build` from `frontend`.

---

### Task 1: Citation Formatting Utilities

**Files:**
- Create: `frontend/src/utils/citations.ts`
- Verify: `frontend/package.json`

- [ ] **Step 1: Create the utility module**

Create `frontend/src/utils/citations.ts` with this content:

```ts
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
```

- [ ] **Step 2: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully with `built in` in the output.

- [ ] **Step 3: Commit Task 1**

Run:

```powershell
git add frontend/src/utils/citations.ts
git commit -m "feat: add citation formatting helpers"
```

Expected: one commit containing only `frontend/src/utils/citations.ts`.

---

### Task 2: Retrieval Metrics Component

**Files:**
- Create: `frontend/src/components/RetrievalMetrics.tsx`
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Create the metrics component**

Create `frontend/src/components/RetrievalMetrics.tsx` with this content:

```tsx
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
```

- [ ] **Step 2: Add metric styles**

Append this block near the existing citation styles in `frontend/src/styles.css`:

```css
.retrieval-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.retrieval-metrics.compact {
  gap: 4px;
}

.metric-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 22px;
  max-width: 100%;
  border: 1px solid var(--panel-border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--panel) 82%, transparent);
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  padding: 4px 8px;
  white-space: nowrap;
}

.metric-badge .material-symbols-outlined {
  font-size: 14px;
}

.metric-badge-label {
  color: var(--muted);
}

.metric-badge-value {
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.metric-badge-score {
  position: relative;
}

.metric-badge-path {
  color: var(--on-secondary-container);
  background: var(--accent-soft);
}

.metric-badge-context {
  color: var(--warning);
  background: var(--warning-soft);
}

.metric-score-bar {
  width: 42px;
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--panel-high);
}

.metric-score-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--success);
}
```

- [ ] **Step 3: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 4: Commit Task 2**

Run:

```powershell
git add frontend/src/components/RetrievalMetrics.tsx frontend/src/styles.css
git commit -m "feat: add retrieval metrics display"
```

Expected: one commit containing the metrics component and styles.

---

### Task 3: Inline Citation Pills

**Files:**
- Create: `frontend/src/components/CitationText.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Create the citation text renderer**

Create `frontend/src/components/CitationText.tsx` with this content:

```tsx
import type { SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  findCitationEntryByLabel,
  formatPageRange,
  formatSectionPath,
  getSourceKey,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";

interface CitationTextProps {
  answer: string;
  sources: SourceCitation[];
  selectedSourceChunkId: string | null;
  onSelectSource: (source: SourceCitation) => void;
}

const CITATION_PATTERN = /\[([^\[\]\s]{1,32})\]/g;

export default function CitationText({
  answer,
  sources,
  selectedSourceChunkId,
  onSelectSource,
}: CitationTextProps) {
  const entries = buildCitationEntries(sources);
  const parts: Array<string | JSX.Element> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = CITATION_PATTERN.exec(answer)) !== null) {
    const [fullMatch, rawLabel] = match;
    const entry = findCitationEntryByLabel(entries, rawLabel);

    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }

    if (!entry) {
      parts.push(fullMatch);
    } else {
      const { source, label } = entry;
      const isSelected = source.chunk_id === selectedSourceChunkId;
      const pageRange = formatPageRange(source.page_start, source.page_end);
      const sectionPath = formatSectionPath(source.section_path);
      const preview =
        source.content_preview?.trim() || "Preview text was not returned for this citation.";

      parts.push(
        <span className="citation-pill-wrap" key={`${getSourceKey(source)}:${match.index}`}>
          <button
            className={`citation-pill ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectSource(source)}
            aria-label={`Open citation ${label} from ${source.file_name}, ${pageRange}`}
          >
            [{label}]
          </button>
          <span className="citation-popover" role="tooltip">
            <span className="citation-popover-title">{source.file_name}</span>
            <span className="citation-popover-meta">
              {pageRange} - Chunk {source.chunk_index}
            </span>
            <span className="citation-popover-meta">{sectionPath}</span>
            <span className="citation-popover-preview">{preview}</span>
            <RetrievalMetrics source={source} compact />
          </span>
        </span>,
      );
    }

    lastIndex = match.index + fullMatch.length;
  }

  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return <span className="citation-text">{parts}</span>;
}
```

- [ ] **Step 2: Wire `CitationText` into `ChatPanel.tsx`**

In `frontend/src/components/ChatPanel.tsx`, add this import:

```tsx
import CitationText from "./CitationText";
```

Replace the AI answer block:

```tsx
<div className="chat-bubble-content">
  {response.answer}
</div>
```

with:

```tsx
<div className="chat-bubble-content chat-bubble-content-ai-response">
  <CitationText
    answer={response.answer}
    sources={response.sources ?? []}
    selectedSourceChunkId={selectedSource?.chunk_id ?? null}
    onSelectSource={onSelectSource}
  />
</div>
```

- [ ] **Step 3: Add citation pill and popover styles**

Replace the existing `.citation-pill` and `.citation-pill:hover` block in `frontend/src/styles.css` with this block:

```css
.citation-text {
  white-space: pre-wrap;
}

.citation-pill-wrap {
  position: relative;
  display: inline-flex;
  vertical-align: baseline;
}

.citation-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 22px;
  margin: 0 3px;
  padding: 2px 7px;
  border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--panel-border));
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--on-secondary-container);
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.citation-pill:hover,
.citation-pill:focus-visible,
.citation-pill.selected {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.citation-pill.selected {
  background: var(--accent);
  color: var(--on-primary);
}

.citation-popover {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 10px);
  z-index: 120;
  display: none;
  width: min(320px, 80vw);
  transform: translateX(-50%);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
  color: var(--text);
  padding: 12px;
  white-space: normal;
}

.citation-pill-wrap:hover .citation-popover,
.citation-pill:focus-visible + .citation-popover {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.citation-popover-title {
  font-size: 12px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-popover-meta {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}

.citation-popover-preview {
  color: var(--text);
  display: -webkit-box;
  font-size: 12px;
  line-height: 1.45;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}
```

- [ ] **Step 4: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add frontend/src/components/CitationText.tsx frontend/src/components/ChatPanel.tsx frontend/src/styles.css
git commit -m "feat: render interactive answer citations"
```

Expected: one commit containing inline citation rendering.

---

### Task 4: Source Cards and Citation Navigator

**Files:**
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Replace `SourceList.tsx`**

Replace the full contents of `frontend/src/components/SourceList.tsx` with:

```tsx
import type { SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  formatChunkLabel,
  formatPageRange,
  formatSectionPath,
  getSourceTitle,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";

interface SourceListProps {
  sources: SourceCitation[];
  selectedSourceChunkId: string | null;
  onSelectSource: (source: SourceCitation) => void;
}

function getFileIcon(fileName: string) {
  const ext = fileName.split(".").pop()?.toLowerCase();
  if (ext === "pdf") {
    return <span className="material-symbols-outlined citation-card-icon">picture_as_pdf</span>;
  }
  if (ext === "docx" || ext === "doc") {
    return <span className="material-symbols-outlined citation-card-icon docx">description</span>;
  }
  if (ext === "txt") {
    return <span className="material-symbols-outlined citation-card-icon txt">article</span>;
  }
  if (ext === "md" || ext === "markdown") {
    return <span className="material-symbols-outlined citation-card-icon md">description</span>;
  }
  return <span className="material-symbols-outlined citation-card-icon">insert_drive_file</span>;
}

export default function SourceList({
  sources,
  selectedSourceChunkId,
  onSelectSource,
}: SourceListProps) {
  if (sources.length === 0) {
    return <div className="chat-sources-empty">No sources cited for this response.</div>;
  }

  const entries = buildCitationEntries(sources);

  return (
    <div className="chat-sources-list" role="list">
      {entries.map(({ source, label, sourceKey }) => {
        const isSelected = source.chunk_id === selectedSourceChunkId;
        const pageInfo = formatPageRange(source.page_start, source.page_end);
        const sectionPath = formatSectionPath(source.section_path);

        return (
          <button
            key={sourceKey}
            className={`citation-card ${isSelected ? "selected" : ""}`}
            type="button"
            onClick={() => onSelectSource(source)}
            aria-label={`View citation ${label} from ${getSourceTitle(source)}`}
          >
            <span className="citation-card-label">[{label}]</span>
            {getFileIcon(source.file_name)}
            <span className="citation-card-details">
              <span className="citation-card-name" title={source.file_name}>
                {source.file_name}
              </span>
              <span className="citation-card-meta">
                {pageInfo} - {formatChunkLabel(source)}
              </span>
              <span className="citation-card-meta" title={sectionPath}>
                {sectionPath}
              </span>
              <RetrievalMetrics source={source} compact />
            </span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Update source card CSS**

Replace the existing `.citation-card`, `.citation-card:hover`, `.citation-card.selected`, `.citation-card-details`, `.citation-card-name`, and `.citation-card-meta` blocks in `frontend/src/styles.css` with:

```css
.citation-card {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  width: min(100%, 360px);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--panel) 88%, transparent);
  box-shadow: var(--shadow);
  cursor: pointer;
  padding: 12px;
  text-align: left;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.citation-card:hover,
.citation-card:focus-visible {
  background: var(--panel-soft);
  border-color: color-mix(in srgb, var(--accent) 30%, var(--panel-border));
  transform: translateY(-1px);
}

.citation-card.selected {
  background: var(--accent-soft);
  border-color: color-mix(in srgb, var(--accent) 50%, var(--panel-border));
}

.citation-card-label {
  border-radius: 999px;
  background: var(--accent);
  color: var(--on-primary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  padding: 5px 7px;
}

.citation-card-details {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.citation-card-name {
  color: var(--text);
  font-size: 12px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-card-meta {
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

- [ ] **Step 3: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 4: Commit Task 4**

Run:

```powershell
git add frontend/src/components/SourceList.tsx frontend/src/styles.css
git commit -m "feat: improve source citation cards"
```

Expected: one commit containing the updated source list UI.

---

### Task 5: References Drawer

**Files:**
- Create: `frontend/src/components/ReferencesDrawer.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Create `ReferencesDrawer.tsx`**

Create `frontend/src/components/ReferencesDrawer.tsx` with this content:

```tsx
import type { DocumentChunk, SourceCitation } from "../api/types";
import {
  buildCitationEntries,
  formatChunkLabel,
  formatPageRange,
  formatSectionPath,
  getSourceTitle,
} from "../utils/citations";
import ChunkViewerPanel from "./ChunkViewerPanel";
import RetrievalMetrics from "./RetrievalMetrics";

interface ReferencesDrawerProps {
  sources: SourceCitation[];
  selectedSource: SourceCitation | null;
  selectedChunk: DocumentChunk | null;
  isLoading: boolean;
  error: string | null;
  hasPreviousChunk: boolean;
  hasNextChunk: boolean;
  onSelectSource: (source: SourceCitation) => void;
  onClose: () => void;
  onViewPreviousChunk: () => void;
  onViewNextChunk: () => void;
}

export default function ReferencesDrawer({
  sources,
  selectedSource,
  selectedChunk,
  isLoading,
  error,
  hasPreviousChunk,
  hasNextChunk,
  onSelectSource,
  onClose,
  onViewPreviousChunk,
  onViewNextChunk,
}: ReferencesDrawerProps) {
  const isOpen = selectedSource !== null;
  const entries = buildCitationEntries(sources);

  return (
    <aside className={`app-preview-panel references-drawer ${isOpen ? "open" : ""}`}>
      <div className="preview-panel-header">
        <div className="preview-panel-header-title">
          <span className="material-symbols-outlined">fact_check</span>
          <h2>{selectedSource?.file_name ?? "References"}</h2>
        </div>
        <button
          className="preview-close-button"
          onClick={onClose}
          aria-label="Close references drawer"
          type="button"
        >
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      <div className="references-drawer-content">
        <div className="references-navigator" aria-label="Retrieved sources">
          <div className="references-navigator-header">
            <span>Retrieved Sources</span>
            <span>{entries.length}</span>
          </div>

          {entries.length === 0 ? (
            <div className="references-empty">No retrieved chunks for this answer.</div>
          ) : (
            <div className="references-source-stack">
              {entries.map(({ source, label, sourceKey }) => {
                const isSelected =
                  selectedSource?.chunk_id === source.chunk_id &&
                  selectedSource?.document_id === source.document_id;
                const sectionPath = formatSectionPath(source.section_path);

                return (
                  <button
                    key={sourceKey}
                    className={`references-source-button ${isSelected ? "selected" : ""}`}
                    type="button"
                    onClick={() => onSelectSource(source)}
                    aria-label={`Open citation ${label} from ${getSourceTitle(source)}`}
                  >
                    <span className="references-source-topline">
                      <span className="references-source-label">[{label}]</span>
                      <span>{formatPageRange(source.page_start, source.page_end)}</span>
                    </span>
                    <span className="references-source-title" title={source.file_name}>
                      {source.file_name}
                    </span>
                    <span className="references-source-meta" title={sectionPath}>
                      {sectionPath} - {formatChunkLabel(source)}
                    </span>
                    <RetrievalMetrics source={source} compact />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="references-active-panel">
          <ChunkViewerPanel
            selectedSource={selectedSource}
            selectedChunk={selectedChunk}
            isLoading={isLoading}
            error={error}
            hasPreviousChunk={hasPreviousChunk}
            hasNextChunk={hasNextChunk}
            onViewPreviousChunk={onViewPreviousChunk}
            onViewNextChunk={onViewNextChunk}
          />
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Wire the drawer in `App.tsx`**

In `frontend/src/App.tsx`, replace:

```tsx
import ChunkViewerPanel from "./components/ChunkViewerPanel";
```

with:

```tsx
import ReferencesDrawer from "./components/ReferencesDrawer";
```

Then replace the full `<aside className={`app-preview-panel ...`}>...</aside>` block at the end of the component with:

```tsx
<ReferencesDrawer
  sources={chat.response.sources ?? []}
  selectedSource={chunks.selectedSource}
  selectedChunk={chunks.selectedChunk}
  isLoading={chunks.isLoading}
  error={chunks.error}
  hasPreviousChunk={chunks.hasPreviousChunk}
  hasNextChunk={chunks.hasNextChunk}
  onSelectSource={chunks.selectSource}
  onClose={chunks.clearSelection}
  onViewPreviousChunk={chunks.viewPreviousChunk}
  onViewNextChunk={chunks.viewNextChunk}
/>
```

- [ ] **Step 3: Add drawer styles**

Append this block before the responsive media queries in `frontend/src/styles.css`:

```css
.references-drawer.open {
  width: min(560px, 42vw);
}

.references-drawer-content {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  min-height: 0;
  height: 100%;
}

.references-navigator {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
  border-right: 1px solid var(--panel-border);
  background: var(--panel-soft);
  padding: 16px;
  overflow-y: auto;
}

.references-navigator-header {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.references-source-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.references-source-button {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  cursor: pointer;
  padding: 10px;
  text-align: left;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.references-source-button:hover,
.references-source-button:focus-visible,
.references-source-button.selected {
  border-color: color-mix(in srgb, var(--accent) 42%, var(--panel-border));
  transform: translateY(-1px);
}

.references-source-button.selected {
  background: var(--accent-soft);
}

.references-source-topline {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
}

.references-source-label {
  color: var(--accent);
}

.references-source-title {
  overflow: hidden;
  color: var(--text);
  font-size: 12px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.references-source-meta {
  overflow: hidden;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.references-active-panel {
  min-width: 0;
  overflow-y: auto;
  padding: 20px;
}

.references-empty {
  border: 1px dashed var(--panel-border);
  border-radius: 8px;
  color: var(--muted);
  font-size: 12px;
  padding: 12px;
}
```

- [ ] **Step 4: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add frontend/src/components/ReferencesDrawer.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: add references drawer navigator"
```

Expected: one commit containing drawer creation and App wiring.

---

### Task 6: Chunk Preview Metadata Upgrade

**Files:**
- Modify: `frontend/src/components/ChunkViewerPanel.tsx`
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Import shared helpers and metrics**

In `frontend/src/components/ChunkViewerPanel.tsx`, add:

```tsx
import {
  formatPageRange,
  formatRawScore,
  formatRetrievalPaths,
  formatSectionPath,
} from "../utils/citations";
import RetrievalMetrics from "./RetrievalMetrics";
```

Remove the local `formatPageRange` and `formatScore` functions from the file.

- [ ] **Step 2: Update derived metadata values**

Replace the existing metadata derivation block:

```tsx
const scoreVal = selectedSource.rerank_score ?? selectedSource.qdrant_score;
const relevanceStr = formatScore(scoreVal);

const pageRange =
  formatPageRange(selectedChunk.page_start, selectedChunk.page_end) ??
  formatPageRange(selectedSource.page_start, selectedSource.page_end) ??
  "N/A";
const heading = selectedChunk.heading ?? selectedSource.heading ?? "N/A";
const sectionPath =
  selectedChunk.section_path && selectedChunk.section_path.length > 0
    ? selectedChunk.section_path.join(" / ")
    : "N/A";
```

with:

```tsx
const primaryScore =
  selectedSource.rerank_score ?? selectedSource.fusion_score ?? selectedSource.qdrant_score;
const relevanceStr = formatRawScore(primaryScore);
const pageRange = formatPageRange(
  selectedChunk.page_start ?? selectedSource.page_start,
  selectedChunk.page_end ?? selectedSource.page_end,
);
const heading = selectedChunk.heading ?? selectedSource.heading ?? "No heading";
const sectionPath = formatSectionPath(
  selectedChunk.section_path?.length ? selectedChunk.section_path : selectedSource.section_path,
);
const retrievalPaths = formatRetrievalPaths(selectedSource.retrieval_paths);
```

- [ ] **Step 3: Add metrics under the fragment header**

Inside the `.preview-fragment-card`, immediately after the `.preview-fragment-header` closing `</div>`, add:

```tsx
<RetrievalMetrics source={selectedSource} />
```

- [ ] **Step 4: Add metadata cards for all retrieval scores**

Inside `.preview-metadata-grid`, after the existing Qdrant Score card, add:

```tsx
<div className="preview-metadata-card">
  <span className="preview-metadata-label">Rerank Score</span>
  <span className="preview-metadata-value">
    {formatRawScore(selectedSource.rerank_score)}
  </span>
</div>

<div className="preview-metadata-card">
  <span className="preview-metadata-label">Fusion Score</span>
  <span className="preview-metadata-value">
    {formatRawScore(selectedSource.fusion_score)}
  </span>
</div>

<div className="preview-metadata-card preview-metadata-card-wide">
  <span className="preview-metadata-label">Retrieval Path</span>
  <span className="preview-metadata-value" title={retrievalPaths}>
    {retrievalPaths}
  </span>
</div>
```

Then replace the Qdrant score value:

```tsx
{selectedSource.qdrant_score !== null ? selectedSource.qdrant_score.toFixed(4) : "N/A"}
```

with:

```tsx
{formatRawScore(selectedSource.qdrant_score)}
```

- [ ] **Step 5: Remove premium disabled action**

Delete this footer block from `ChunkViewerPanel.tsx`:

```tsx
<div className="preview-full-doc-container">
  <button 
    className="btn-outline" 
    disabled 
    title="Full document viewer requires premium document integration."
  >
    <span className="material-symbols-outlined">open_in_new</span>
    Open Full Document
  </button>
</div>
```

Reason: the new drawer focuses on retrieved chunks and adjacent context; disabled premium UI is unrelated to RAG evidence inspection.

- [ ] **Step 6: Add wide metadata card CSS**

Append this style near `.preview-metadata-card` in `frontend/src/styles.css`:

```css
.preview-metadata-card-wide {
  grid-column: 1 / -1;
}
```

- [ ] **Step 7: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 8: Commit Task 6**

Run:

```powershell
git add frontend/src/components/ChunkViewerPanel.tsx frontend/src/styles.css
git commit -m "feat: expand chunk retrieval metadata"
```

Expected: one commit containing metadata visualization only.

---

### Task 7: Glassmorphism, Dark Mode, and Motion

**Files:**
- Modify: `frontend/src/styles.css`
- Verify: `frontend/package.json`

- [ ] **Step 1: Extend root design tokens**

In `frontend/src/styles.css`, add these variables inside `:root` after `--shadow`:

```css
  --glass-bg: rgba(255, 255, 255, 0.78);
  --glass-border: rgba(148, 163, 184, 0.28);
  --glass-shadow: 0 16px 48px rgba(15, 23, 42, 0.12);
  --motion-fast: 160ms ease;
  --motion-medium: 260ms ease;
```

- [ ] **Step 2: Add dark-mode variables**

Add this block after the `:root` block:

```css
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #0f1419;
    --panel: #151b22;
    --panel-border: #2d3742;
    --panel-soft: #1c242d;
    --panel-high: #26313c;
    --text: #eef2f6;
    --muted: #aab4c0;
    --accent: #d7e2ff;
    --on-primary: #101418;
    --accent-soft: #23314a;
    --on-secondary-container: #d7e2ff;
    --success: #5eead4;
    --success-soft: rgba(20, 184, 166, 0.16);
    --warning: #facc15;
    --warning-soft: rgba(250, 204, 21, 0.14);
    --danger: #fca5a5;
    --danger-soft: rgba(248, 113, 113, 0.14);
    --glass-bg: rgba(21, 27, 34, 0.78);
    --glass-border: rgba(148, 163, 184, 0.2);
    --glass-shadow: 0 20px 60px rgba(0, 0, 0, 0.34);
  }
}
```

- [ ] **Step 3: Apply glass surfaces to existing containers**

Append this block near the main layout styles:

```css
.app-topbar,
.app-sidebar,
.app-preview-panel,
.chat-bubble-row.ai .chat-bubble-content,
.chat-input-bar,
.document-card,
.history-card,
.citation-card,
.preview-fragment-card,
.preview-metadata-card {
  background: var(--glass-bg);
  border-color: var(--glass-border);
  box-shadow: var(--glass-shadow);
  backdrop-filter: blur(18px);
}

@supports not (backdrop-filter: blur(18px)) {
  .app-topbar,
  .app-sidebar,
  .app-preview-panel,
  .chat-bubble-row.ai .chat-bubble-content,
  .chat-input-bar,
  .document-card,
  .history-card,
  .citation-card,
  .preview-fragment-card,
  .preview-metadata-card {
    background: var(--panel);
  }
}
```

- [ ] **Step 4: Add response and drawer animation**

Append this block before responsive media queries:

```css
@keyframes response-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-bubble-row.ai .chat-bubble-body {
  animation: response-enter var(--motion-medium);
}

.app-preview-panel {
  transition: width var(--motion-medium), transform var(--motion-medium), border-color var(--motion-medium);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 1ms !important;
  }
}
```

- [ ] **Step 5: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add frontend/src/styles.css
git commit -m "style: add glass theme and motion polish"
```

Expected: one commit containing centralized styling only.

---

### Task 8: Responsive and Accessibility Pass

**Files:**
- Modify: `frontend/src/styles.css`
- Review: `frontend/src/components/CitationText.tsx`
- Review: `frontend/src/components/ReferencesDrawer.tsx`
- Review: `frontend/src/components/SourceList.tsx`
- Verify: `frontend/package.json`

- [ ] **Step 1: Add mobile drawer layout**

Inside the existing `@media (max-width: 900px)` block in `frontend/src/styles.css`, add:

```css
  .references-drawer.open {
    width: min(100vw, 520px);
  }

  .references-drawer-content {
    grid-template-columns: 1fr;
  }

  .references-navigator {
    max-height: 34vh;
    border-right: none;
    border-bottom: 1px solid var(--panel-border);
  }
```

- [ ] **Step 2: Add compact mobile source cards**

Inside the existing `@media (max-width: 600px)` block, add:

```css
  .chat-sources-list {
    flex-direction: column;
  }

  .citation-card {
    width: 100%;
  }

  .citation-popover {
    left: 0;
    width: min(300px, calc(100vw - 32px));
    transform: none;
  }

  .preview-metadata-grid {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 3: Check accessible labels**

Confirm these button labels exist in code:

```tsx
aria-label={`Open citation ${label} from ${source.file_name}, ${pageRange}`}
aria-label={`View citation ${label} from ${getSourceTitle(source)}`}
aria-label="Close references drawer"
aria-label={`Open citation ${label} from ${getSourceTitle(source)}`}
```

Expected: all citation, source, drawer close, and navigator buttons have explicit labels.

- [ ] **Step 4: Run the frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 5: Commit Task 8**

Run:

```powershell
git add frontend/src/styles.css frontend/src/components/CitationText.tsx frontend/src/components/ReferencesDrawer.tsx frontend/src/components/SourceList.tsx
git commit -m "style: tune reference UI responsiveness"
```

Expected: one commit containing responsive and accessibility polish.

---

### Task 9: End-to-End Manual Verification

**Files:**
- Verify only; no code changes expected.

- [ ] **Step 1: Run final frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build completes successfully.

- [ ] **Step 2: Start the frontend dev server**

Run:

```powershell
cd frontend
npm run dev
```

Expected: Vite prints a local URL such as `http://localhost:5173/`.

- [ ] **Step 3: Verify existing chat state**

In the browser:

```text
1. Open the Vite local URL.
2. Select one or more ready documents.
3. Ask a document question.
4. Confirm the answer appears.
5. Confirm the question input clears after successful submission.
6. Confirm no request URL or API token prompt changed.
```

Expected: existing chat behavior is unchanged.

- [ ] **Step 4: Verify inline citations**

In the browser:

```text
1. Find a response containing bracketed citations such as [S1].
2. Hover a citation pill.
3. Focus the citation pill with the keyboard.
4. Click the citation pill.
```

Expected: the preview popover appears on hover/focus, click opens the references drawer, and the selected citation is highlighted.

- [ ] **Step 5: Verify references drawer**

In the browser:

```text
1. Click each retrieved source in the drawer navigator.
2. Confirm the active chunk content changes.
3. Use Previous and Next chunk buttons.
4. Close the drawer.
```

Expected: source selection uses existing chunk loading, adjacent navigation works from cached document chunks, and closing clears selection.

- [ ] **Step 6: Verify retrieval transparency**

In the browser:

```text
1. Inspect source cards.
2. Inspect citation popovers.
3. Inspect the drawer metadata.
```

Expected: available semantic, rerank, fusion, path, and neighbor-context values render only when present in the API response.

- [ ] **Step 7: Verify history restoration**

In the browser:

```text
1. Open Recent Research.
2. Select a saved message that has sources.
3. Return to the chat view.
4. Click an inline citation or source card.
```

Expected: saved answer and sources render with the same citation and drawer behavior as a fresh chat response.

- [ ] **Step 8: Stop the dev server**

In the terminal running Vite, press:

```text
Ctrl+C
```

Expected: the dev server stops cleanly.

- [ ] **Step 9: Commit final verification note if code changed during verification**

If verification required a small fix, commit the changed files:

```powershell
git add frontend/src
git commit -m "fix: polish reference visualization verification issues"
```

Expected: no commit is created when verification required no code changes.

---

## Self-Review Checklist

- [ ] Interactive citation pills are implemented in Task 3.
- [ ] References drawer and source navigator are implemented in Task 5.
- [ ] Adjacent context navigation keeps using `useChunks.viewPreviousChunk` and `useChunks.viewNextChunk`.
- [ ] Retrieval metric badges and score details are implemented in Tasks 2, 4, and 6.
- [ ] Dark mode, glass styling, and micro-animations are centralized in `styles.css` in Task 7.
- [ ] Mobile and keyboard access are covered in Task 8.
- [ ] Every implementation phase includes `npm run build`.
- [ ] API/chat state logic is explicitly preserved by Safety Rules.
- [ ] No mock credentials, new API endpoints, or fake retrieval values are introduced.
