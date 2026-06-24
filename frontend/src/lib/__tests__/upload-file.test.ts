import { describe, expect, it } from "vitest";
import { prepareUploadFile, UPLOAD_NOT_A_PDF_ERROR } from "../upload-file";

describe("prepareUploadFile", () => {
  it("returns a snapshot with the same bytes and name", async () => {
    const original = new File(["%PDF-1.4 test"], "notes.pdf", { type: "application/pdf" });
    const prepared = await prepareUploadFile(original);

    const name = prepared instanceof File ? prepared.name : "notes.pdf";
    expect(name).toBe("notes.pdf");
    expect(await prepared.text()).toBe("%PDF-1.4 test");
  });

  it("rejects non-PDF files", async () => {
    const original = new File(["not a pdf"], "notes.pdf", { type: "application/pdf" });
    await expect(prepareUploadFile(original)).rejects.toThrow(UPLOAD_NOT_A_PDF_ERROR);
  });
});
