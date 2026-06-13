import { useId, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

export type QuestionValidation = {
  isValid: boolean;
  message: string | null;
  trimmedQuestion: string;
};

export type ChatBoxProps = {
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: (question: string) => void | Promise<void>;
  disabled?: boolean;
  isSubmitting?: boolean;
  label?: string;
  placeholder?: string;
  submitLabel?: string;
  validationMessage?: string | null;
};

export const QUESTION_REQUIRED_MESSAGE =
  "Enter a question before asking about your documents.";

export function validateQuestion(question: string): QuestionValidation {
  const trimmedQuestion = question.trim();

  if (trimmedQuestion.length === 0) {
    return {
      isValid: false,
      message: QUESTION_REQUIRED_MESSAGE,
      trimmedQuestion,
    };
  }

  return {
    isValid: true,
    message: null,
    trimmedQuestion,
  };
}

export function ChatBox({
  question,
  onQuestionChange,
  onSubmit,
  disabled = false,
  isSubmitting = false,
  label = "Question",
  placeholder = "Ask a question about the selected documents",
  submitLabel = "Ask question",
  validationMessage = null,
}: ChatBoxProps) {
  const generatedId = useId();
  const textareaId = `chat-box-${generatedId}`;
  const [internalValidationMessage, setInternalValidationMessage] = useState<
    string | null
  >(null);
  const resolvedValidationMessage =
    validationMessage ?? internalValidationMessage;

  function handleQuestionChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setInternalValidationMessage(null);
    onQuestionChange(event.target.value);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (disabled || isSubmitting) {
      return;
    }

    const validation = validateQuestion(question);

    if (!validation.isValid) {
      setInternalValidationMessage(validation.message);
      return;
    }

    setInternalValidationMessage(null);
    void onSubmit(validation.trimmedQuestion);
  }

  return (
    <form
      className="chat-box"
      aria-busy={isSubmitting ? "true" : "false"}
      onSubmit={handleSubmit}
    >
      <label className="chat-box__label" htmlFor={textareaId}>
        {label}
      </label>
      <textarea
        className="chat-box__textarea"
        disabled={disabled || isSubmitting}
        id={textareaId}
        onChange={handleQuestionChange}
        placeholder={placeholder}
        rows={4}
        value={question}
      />

      {resolvedValidationMessage ? (
        <p className="chat-box__validation" role="alert">
          {resolvedValidationMessage}
        </p>
      ) : null}

      <button
        className="chat-box__submit"
        disabled={disabled || isSubmitting}
        type="submit"
      >
        {isSubmitting ? "Asking..." : submitLabel}
      </button>
    </form>
  );
}
