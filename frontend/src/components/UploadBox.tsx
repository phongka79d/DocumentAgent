import { useId, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  SUPPORTED_FILE_ACCEPT,
  validateSelectedFile,
} from "../utils/fileValidation";

export type UploadBoxProps = {
  disabled?: boolean;
  id?: string;
  label?: string;
  selectedFile?: File | null;
  onFileSelect: (file: File) => void;
};

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadBox({
  disabled = false,
  id,
  label = "Choose a document",
  selectedFile,
  onFileSelect,
}: UploadBoxProps) {
  const generatedId = useId();
  const inputId = id ?? `upload-box-${generatedId}`;
  const [internalSelectedFile, setInternalSelectedFile] = useState<File | null>(
    null,
  );
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const displayedFile =
    selectedFile === undefined ? internalSelectedFile : selectedFile;

  function selectFile(file: File | undefined) {
    if (!file || disabled) {
      return;
    }

    const validation = validateSelectedFile(file);
    if (!validation.isValid) {
      setValidationMessage(validation.message);
      setInternalSelectedFile(null);
      return;
    }

    setValidationMessage(null);
    setInternalSelectedFile(file);
    onFileSelect(file);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    if (disabled) {
      return;
    }

    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setIsDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }

    setIsDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    if (disabled) {
      return;
    }

    event.preventDefault();
    setIsDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div className="upload-box">
      <label
        className={[
          "upload-box__dropzone",
          isDragging ? "upload-box__dropzone--dragging" : "",
          disabled ? "upload-box__dropzone--disabled" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        htmlFor={inputId}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <span className="upload-box__label">{label}</span>
        <span className="upload-box__hint">
          Select or drop a PDF, DOCX, TXT, or CSV file.
        </span>
        <input
          accept={SUPPORTED_FILE_ACCEPT}
          className="upload-box__input"
          disabled={disabled}
          id={inputId}
          onChange={handleInputChange}
          type="file"
        />
      </label>

      {displayedFile ? (
        <p className="upload-box__feedback" aria-live="polite">
          Selected: <strong>{displayedFile.name}</strong>{" "}
          <span>({formatFileSize(displayedFile.size)})</span>
        </p>
      ) : null}

      {validationMessage ? (
        <p className="upload-box__error" aria-live="polite">
          {validationMessage}
        </p>
      ) : null}
    </div>
  );
}
