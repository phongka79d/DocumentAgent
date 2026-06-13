import { useId } from "react";

export type JsonViewerProps = {
  label: string;
  value: unknown;
};

const SERIALIZATION_FALLBACK = "Unable to serialize this value as JSON.";

function formatJsonValue(value: unknown): string {
  if (value === undefined) {
    return "undefined";
  }

  if (typeof value === "bigint") {
    return `${value.toString()}n`;
  }

  if (typeof value === "function") {
    return "[Unsupported value: function]";
  }

  if (typeof value === "symbol") {
    return "[Unsupported value: symbol]";
  }

  try {
    return JSON.stringify(value, null, 2) ?? SERIALIZATION_FALLBACK;
  } catch {
    return SERIALIZATION_FALLBACK;
  }
}

export function JsonViewer({ label, value }: JsonViewerProps) {
  const generatedId = useId();
  const labelId = `json-viewer-label-${generatedId}`;

  return (
    <section className="json-viewer" aria-labelledby={labelId}>
      <h3 className="json-viewer__label" id={labelId}>
        {label}
      </h3>
      <div className="json-viewer__scroll">
        <pre className="json-viewer__content">{formatJsonValue(value)}</pre>
      </div>
    </section>
  );
}
