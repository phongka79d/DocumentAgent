import { useRef, useState, type ChangeEvent, type FormEvent } from "react";

const ACCEPTED_FILE_TYPES =
  ".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown";

interface UploadPanelProps {
  isUploading: boolean;
  error: string | null;
  result: string | null;
  onUpload: (file: File) => Promise<void>;
}

export default function UploadPanel({
  error,
  isUploading,
  onUpload,
  result,
}: UploadPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile || isUploading) {
      return;
    }

    await onUpload(selectedFile);
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  const statusMessage = isUploading
    ? "Uploading"
    : error ?? result ?? null;

  return (
    <section className="panel upload-panel" aria-label="Upload document">
      <div className="panel-heading">
        <h2>Upload</h2>
      </div>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">File</span>
          <input
            ref={fileInputRef}
            className="file-input"
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </label>

        <div className="upload-footer">
          <button
            className="button button--primary"
            type="submit"
            disabled={!selectedFile || isUploading}
            aria-busy={isUploading}
          >
            {isUploading ? (
              <span className="button-spinner" aria-hidden="true" />
            ) : null}
            <span>{isUploading ? "Uploading" : "Upload"}</span>
          </button>

          <div className="upload-status" aria-live="polite">
            <div
              className="upload-selection"
              title={selectedFile?.name ?? "No file selected"}
            >
              {selectedFile ? selectedFile.name : "No file selected"}
            </div>

          <div
            className={`upload-feedback ${
              isUploading
                ? "upload-feedback--loading"
                : error
                  ? "upload-feedback--error"
                  : result
                    ? "upload-feedback--success"
                    : "upload-feedback--idle"
            }`}
            >
              {statusMessage ? (
                <>
                  {isUploading ? (
                    <span className="button-spinner" aria-hidden="true" />
                  ) : null}
                  <span>{statusMessage}</span>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </form>
    </section>
  );
}
