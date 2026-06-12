import type { DocumentStatus } from "../types/documents";

type StatusBadgeProps = {
  status: DocumentStatus;
};

const STATUS_BADGE_CONTENT = {
  uploaded: {
    label: "Uploaded",
    className: "status-badge--uploaded",
  },
  processing: {
    label: "Processing",
    className: "status-badge--processing",
  },
  ready: {
    label: "Ready",
    className: "status-badge--ready",
  },
  failed: {
    label: "Failed",
    className: "status-badge--failed",
  },
} satisfies Record<DocumentStatus, { label: string; className: string }>;

export function StatusBadge({ status }: StatusBadgeProps) {
  const content = STATUS_BADGE_CONTENT[status];

  return (
    <span
      aria-label={`Document status: ${content.label}`}
      className={`status-badge ${content.className}`}
      title={content.label}
    >
      <span aria-hidden="true" className="status-badge__indicator" />
      <span className="status-badge__text">{content.label}</span>
    </span>
  );
}
