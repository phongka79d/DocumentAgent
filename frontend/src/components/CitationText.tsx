import { useState, useRef } from "react";
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

interface CitationPillProps {
  source: SourceCitation;
  label: string;
  isSelected: boolean;
  onSelectSource: (source: SourceCitation) => void;
  matchIndex: number;
}

function CitationPill({
  source,
  label,
  isSelected,
  onSelectSource,
  matchIndex,
}: CitationPillProps) {
  const [align, setAlign] = useState<"left" | "right" | "center">("center");
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  const pageRange = formatPageRange(source.page_start, source.page_end);
  const sectionPath = formatSectionPath(source.section_path);
  const preview =
    source.content_preview?.trim() || "Preview text was not returned for this citation.";

  const updateAlignment = () => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const center = rect.left + rect.width / 2;
    const popoverHalfWidth = 160;

    // Sidebar is ~260px wide, so we want the popover left edge to be >= 280px to avoid clipping on the left.
    if (center - popoverHalfWidth < 280) {
      setAlign("left");
    } else if (center + popoverHalfWidth > window.innerWidth - 40) {
      setAlign("right");
    } else {
      setAlign("center");
    }
  };

  const getPopoverStyle = () => {
    if (align === "left") {
      return { left: "0", transform: "none" };
    }
    if (align === "right") {
      return { right: "0", left: "auto", transform: "none" };
    }
    return {};
  };

  return (
    <span
      className="citation-pill-wrap"
      onMouseEnter={updateAlignment}
    >
      <button
        ref={buttonRef}
        className={`citation-pill ${isSelected ? "selected" : ""}`}
        type="button"
        onClick={() => onSelectSource(source)}
        aria-label={`Open citation ${label} from ${source.file_name}, ${pageRange}`}
        onFocus={updateAlignment}
      >
        [{label}]
      </button>
      <span className="citation-popover" role="tooltip" style={getPopoverStyle()}>
        <span className="citation-popover-title">{source.file_name}</span>
        <span className="citation-popover-meta">
          {pageRange} - Chunk {source.chunk_index}
        </span>
        <span className="citation-popover-meta">{sectionPath}</span>
        <span className="citation-popover-preview">{preview}</span>
        <RetrievalMetrics source={source} compact />
      </span>
    </span>
  );
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

      parts.push(
        <CitationPill
          key={`${getSourceKey(source)}:${match.index}`}
          source={source}
          label={label}
          isSelected={isSelected}
          onSelectSource={onSelectSource}
          matchIndex={match.index}
        />,
      );
    }

    lastIndex = match.index + fullMatch.length;
  }

  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return <span className="citation-text">{parts}</span>;
}
