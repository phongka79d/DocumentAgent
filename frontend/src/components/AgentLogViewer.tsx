import {
  Component,
  useEffect,
  useId,
  useState,
  type ReactNode,
} from "react";

import { AGENT_STEP_NAMES, type AgentStep } from "../types/agentRuns";
import { JsonViewer } from "./JsonViewer";
import { RetrievalScoreTable } from "./RetrievalScoreTable";
import { SelfCheckPanel } from "./SelfCheckPanel";
import { VerificationResultPanel } from "./VerificationResultPanel";

type AgentLogViewerProps = {
  steps: AgentStep[];
};

type SelectedStep = {
  index: number;
  step: AgentStep;
};

type SpecializedPanelKind = "retrieval" | "verification" | "answerSelfCheck";

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "medium",
});

const LEGACY_AGENT_PANEL_KINDS: Record<string, SpecializedPanelKind> = {
  retrieval_agent: "retrieval",
  verification_agent: "verification",
  answer_agent: "answerSelfCheck",
};

function firstSelection(steps: AgentStep[]): SelectedStep | null {
  const step = steps[0];
  return step ? { index: 0, step } : null;
}

function formatTimestamp(timestamp: string): string {
  const parsedTimestamp = new Date(timestamp);
  return Number.isNaN(parsedTimestamp.getTime())
    ? timestamp
    : timestampFormatter.format(parsedTimestamp);
}

function StepTimestamp({ timestamp }: { timestamp: string }) {
  return (
    <time dateTime={timestamp} title={`Raw timestamp: ${timestamp}`}>
      {formatTimestamp(timestamp)}
    </time>
  );
}

function getSpecializedPanelKind(step: AgentStep): SpecializedPanelKind | null {
  switch (step.step_name) {
    case AGENT_STEP_NAMES.retrieval:
      return "retrieval";
    case AGENT_STEP_NAMES.verification:
      return "verification";
    case AGENT_STEP_NAMES.answerSelfCheck:
      return "answerSelfCheck";
    default:
      // Compatibility only for legacy rows that predate reliable step names.
      return LEGACY_AGENT_PANEL_KINDS[step.agent_name] ?? null;
  }
}

function SpecializedPanel({
  kind,
  output,
}: {
  kind: SpecializedPanelKind;
  output: unknown;
}) {
  switch (kind) {
    case "retrieval":
      return <RetrievalScoreTable output={output} />;
    case "verification":
      return <VerificationResultPanel output={output} />;
    case "answerSelfCheck":
      return <SelfCheckPanel output={output} />;
  }
}

type SpecializedPanelBoundaryProps = {
  children: ReactNode;
  resetKey: string;
};

type SpecializedPanelBoundaryState = {
  hasError: boolean;
};

class SpecializedPanelBoundary extends Component<
  SpecializedPanelBoundaryProps,
  SpecializedPanelBoundaryState
> {
  state: SpecializedPanelBoundaryState = { hasError: false };

  static getDerivedStateFromError(): SpecializedPanelBoundaryState {
    return { hasError: true };
  }

  componentDidUpdate(previousProps: SpecializedPanelBoundaryProps) {
    if (
      this.state.hasError &&
      previousProps.resetKey !== this.props.resetKey
    ) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <p
          className="agent-log-viewer__structured-error"
          role="status"
          aria-live="polite"
        >
          Structured step data could not be displayed. Inspect the raw output
          below.
        </p>
      );
    }

    return this.props.children;
  }
}

export function AgentLogViewer({ steps }: AgentLogViewerProps) {
  const viewerId = useId();
  const [selectedStep, setSelectedStep] = useState<SelectedStep | null>(() =>
    firstSelection(steps),
  );

  useEffect(() => {
    setSelectedStep(firstSelection(steps));
  }, [steps]);

  const activeSelection =
    selectedStep && steps[selectedStep.index] === selectedStep.step
      ? selectedStep
      : firstSelection(steps);
  const activeStep = activeSelection?.step ?? null;
  const activeStepIndex = activeSelection?.index ?? -1;
  const specializedPanelKind =
    activeStep?.status === "success"
      ? getSpecializedPanelKind(activeStep)
      : null;
  const emptyHeadingId = `${viewerId}-empty-heading`;
  const stepHeadingId = `${viewerId}-step-heading`;
  const detailId = `${viewerId}-detail`;
  const detailHeadingId = `${viewerId}-detail-heading`;

  if (steps.length === 0) {
    return (
      <section
        className="agent-log-viewer agent-log-viewer--empty"
        aria-labelledby={emptyHeadingId}
      >
        <div className="agent-log-viewer__empty" role="status">
          <h2 id={emptyHeadingId}>No agent steps</h2>
          <p>This run has no persisted steps to inspect.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="agent-log-viewer" aria-label="Agent run steps">
      <nav
        className="agent-log-viewer__step-navigation"
        aria-labelledby={stepHeadingId}
      >
        <h2 id={stepHeadingId}>Agent steps</h2>
        <ol className="agent-log-viewer__step-list">
          {steps.map((step, index) => {
            const isSelected =
              activeSelection?.index === index && activeSelection.step === step;
            const hasError = step.error_message !== null;

            return (
              <li
                className="agent-log-viewer__step-item"
                key={`${index}:${step.agent_name}:${step.step_name}:${step.created_at}`}
              >
                <button
                  type="button"
                  className={`agent-log-viewer__step-control${
                    isSelected ? " agent-log-viewer__step-control--selected" : ""
                  }`}
                  aria-pressed={isSelected}
                  aria-controls={detailId}
                  onClick={() => setSelectedStep({ index, step })}
                >
                  <span className="agent-log-viewer__step-heading">
                    <span className="agent-log-viewer__agent-name">
                      {step.agent_name}
                    </span>
                    {isSelected ? (
                      <span className="agent-log-viewer__selected-indicator">
                        Selected
                      </span>
                    ) : null}
                  </span>
                  <span className="agent-log-viewer__step-name">
                    {step.step_name}
                  </span>
                  <span className="agent-log-viewer__step-metadata">
                    <span
                      className={`agent-log-viewer__status agent-log-viewer__status--${step.status}`}
                    >
                      Status:{" "}
                      {step.status === "success" ? "Success" : "Failed"}
                    </span>
                    <StepTimestamp timestamp={step.created_at} />
                  </span>
                  {hasError ? (
                    <span className="agent-log-viewer__error-indicator">
                      Error present
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
      {activeStep ? (
        <article
          id={detailId}
          className="agent-log-viewer__detail"
          aria-labelledby={detailHeadingId}
          aria-live="polite"
        >
          <header className="agent-log-viewer__detail-header">
            <div>
              <p className="agent-log-viewer__detail-eyebrow">Selected step</p>
              <h2 id={detailHeadingId}>{activeStep.agent_name}</h2>
            </div>
            <span
              className={`agent-log-viewer__status agent-log-viewer__status--${activeStep.status}`}
            >
              Status:{" "}
              {activeStep.status === "success" ? "Success" : "Failed"}
            </span>
          </header>

          <dl className="agent-log-viewer__detail-metadata">
            <div>
              <dt>Step name</dt>
              <dd>{activeStep.step_name}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>
                <StepTimestamp timestamp={activeStep.created_at} />
              </dd>
            </div>
          </dl>

          {activeStep.error_message !== null ? (
            <section
              className="agent-log-viewer__detail-error"
              aria-label="Step error"
              role="alert"
            >
              <h3>Error message</h3>
              <p>{activeStep.error_message}</p>
            </section>
          ) : null}

          {specializedPanelKind ? (
            <div className="agent-log-viewer__structured-panel">
              <SpecializedPanelBoundary
                resetKey={`${activeStepIndex}:${activeStep.step_name}:${activeStep.created_at}`}
              >
                <SpecializedPanel
                  kind={specializedPanelKind}
                  output={activeStep.output}
                />
              </SpecializedPanelBoundary>
            </div>
          ) : null}

          <div className="agent-log-viewer__raw-data">
            <JsonViewer label="Raw input" value={activeStep.input} />
            <JsonViewer label="Raw output" value={activeStep.output} />
          </div>
        </article>
      ) : null}
    </section>
  );
}
