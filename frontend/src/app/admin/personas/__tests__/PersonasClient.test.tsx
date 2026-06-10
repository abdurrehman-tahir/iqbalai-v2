import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PersonasClient } from "../PersonasClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
const mockUpdate = vi.fn();
vi.mock("@/lib/api", () => ({
  personasApi: {
    list: (...a: unknown[]) => mockList(...a),
    update: (...a: unknown[]) => mockUpdate(...a),
  },
}));

const PERSONAS = [
  {
    id: "p1",
    name: "Strict",
    slug: "strict",
    system_prompt_en: "Be strict.",
    is_custom: false,
    is_active: true,
    created_at: "",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PersonasClient — four UI states (T-235)", () => {
  it("loading: shows page heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<PersonasClient />);
    expect(screen.getByRole("heading", { level: 1, name: "title" })).toBeInTheDocument();
  });

  it("error: shows error state with heading", async () => {
    mockList.mockRejectedValue(new Error("fail"));
    renderWithQuery(<PersonasClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("empty: shows empty state with heading", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<PersonasClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("success: lists persona cards", async () => {
    mockList.mockResolvedValue(PERSONAS);
    renderWithQuery(<PersonasClient />);
    await waitFor(() => expect(screen.getByText("Strict")).toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 1, name: "title" })).toBeInTheDocument();
  });

  it("opens edit modal on card action", async () => {
    mockList.mockResolvedValue(PERSONAS);
    mockUpdate.mockResolvedValue(PERSONAS[0]);
    const user = userEvent.setup();
    renderWithQuery(<PersonasClient />);
    await waitFor(() => expect(screen.getByText("edit_button")).toBeInTheDocument());
    await user.click(screen.getByText("edit_button"));
    expect(screen.getByText("modal.title")).toBeInTheDocument();
  });
});
