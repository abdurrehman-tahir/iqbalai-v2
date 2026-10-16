import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../messages/en/common.json";
import { MaterialUploadPanel } from "../MaterialUploadPanel";

const mocks = vi.hoisted(() => ({
  listMaterials: vi.fn(),
  typedMaterial: vi.fn(),
  uploadMaterial: vi.fn(),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/components/shared/HybridInputWidget", () => ({
  HybridInputWidget: ({
    onSubmit,
  }: {
    onSubmit: (p: { text: string; attached_images: [] }) => Promise<void>;
  }) => (
    <button
      type="button"
      data-testid="mock-typed-widget"
      onClick={() => void onSubmit({ text: "Newton laws", attached_images: [] })}
    >
      type-submit
    </button>
  ),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    selfStudyApi: {
      listMaterials: mocks.listMaterials,
      typedMaterial: mocks.typedMaterial,
      uploadMaterial: mocks.uploadMaterial,
    },
  };
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("MaterialUploadPanel (T-212)", () => {
  beforeEach(() => {
    mocks.listMaterials.mockReset();
    mocks.typedMaterial.mockReset();
    mocks.uploadMaterial.mockReset();
    mocks.listMaterials.mockResolvedValue({ items: [] });
  });

  it("shows empty library and four tabs", async () => {
    wrap(<MaterialUploadPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("material-library-empty")).toBeInTheDocument();
    });
    expect(screen.getByTestId("material-tab-pdf")).toBeInTheDocument();
    expect(screen.getByTestId("material-tab-camera")).toBeInTheDocument();
    expect(screen.getByTestId("material-tab-gallery")).toBeInTheDocument();
    expect(screen.getByTestId("material-tab-typed")).toBeInTheDocument();
  });

  it("typed Instant Answer does not claim library save", async () => {
    mocks.typedMaterial.mockResolvedValue({
      disposition: "instant_answer",
      source_type: "typed",
      extraction_method: "typed",
      material: null,
      instant_answer_text: "Here is what I could read…",
      extracted_text_preview: "Newton",
      event_emitted: true,
    });
    wrap(<MaterialUploadPanel />);
    fireEvent.click(screen.getByTestId("material-tab-typed"));
    fireEvent.click(screen.getByTestId("disposition-instant"));
    fireEvent.click(screen.getByTestId("mock-typed-widget"));
    await waitFor(() => {
      expect(screen.getByTestId("material-upload-result")).toHaveTextContent(
        "Here is what I could read",
      );
    });
    expect(screen.queryByTestId("material-library-saved")).toBeNull();
  });
});
