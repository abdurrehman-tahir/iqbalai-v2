export const UPLOAD_FILE_READ_ERROR = "UPLOAD_FILE_READ";
export const UPLOAD_NOT_A_PDF_ERROR = "NOT_A_PDF";

function assertPdfBuffer(buffer: ArrayBuffer): void {
  const bytes = new Uint8Array(buffer.slice(0, 4));
  if (bytes.length < 4 || String.fromCharCode(...bytes) !== "%PDF") {
    throw new Error(UPLOAD_NOT_A_PDF_ERROR);
  }
}

/** Read file bytes with stream fallback (helps iCloud / locked files). */
async function readFileToArrayBuffer(file: File): Promise<ArrayBuffer> {
  try {
    return await file.arrayBuffer();
  } catch {
    const reader = file.stream().getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      total += value.byteLength;
    }
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return merged.buffer;
  }
}

export type UploadFilePayload = File | Blob;

/** Snapshot immediately before upload to avoid ERR_UPLOAD_FILE_CHANGED. */
export async function prepareUploadFile(file: File): Promise<UploadFilePayload> {
  const buffer = await readFileToArrayBuffer(file);
  assertPdfBuffer(buffer);
  const type = file.type || "application/pdf";
  try {
    return new File([buffer], file.name, {
      type,
      lastModified: file.lastModified,
    });
  } catch {
    return new Blob([buffer], { type });
  }
}

/** @deprecated Use prepareUploadFile at submit time instead. */
export async function snapshotUploadFile(file: File): Promise<File> {
  const prepared = await prepareUploadFile(file);
  if (prepared instanceof File) return prepared;
  return new File([await prepared.arrayBuffer()], file.name, {
    type: file.type || "application/pdf",
    lastModified: file.lastModified,
  });
}
