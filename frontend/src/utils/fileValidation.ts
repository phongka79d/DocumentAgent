export const SUPPORTED_FILE_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".csv",
] as const;

export const SUPPORTED_FILE_ACCEPT =
  ".pdf,.docx,.txt,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv";

export const SUPPORTED_FILE_TYPES_MESSAGE =
  "Choose a PDF, DOCX, TXT, or CSV file.";

type FileValidationInput = {
  name: string;
  size?: number;
};

type ValidFileResult = {
  isValid: true;
};

type InvalidFileResult = {
  isValid: false;
  message: string;
  reason: "empty-file" | "unsupported-type";
};

export type FileValidationResult = ValidFileResult | InvalidFileResult;

export function hasSupportedFileExtension(fileName: string) {
  const normalizedName = fileName.trim().toLowerCase();

  return SUPPORTED_FILE_EXTENSIONS.some((extension) =>
    normalizedName.endsWith(extension),
  );
}

export function validateSelectedFile(
  file: FileValidationInput,
): FileValidationResult {
  if (!hasSupportedFileExtension(file.name)) {
    return {
      isValid: false,
      message: `Unsupported file type. ${SUPPORTED_FILE_TYPES_MESSAGE}`,
      reason: "unsupported-type",
    };
  }

  if (file.size === 0) {
    return {
      isValid: false,
      message: `Empty files cannot be uploaded. ${SUPPORTED_FILE_TYPES_MESSAGE}`,
      reason: "empty-file",
    };
  }

  return { isValid: true };
}
