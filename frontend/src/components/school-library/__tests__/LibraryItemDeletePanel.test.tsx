import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { LibraryItemDeletePanel } from "../LibraryItemDeletePanel";

const push = vi.fn();
const deleteItem = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    deleteItem: (...args: unknown[]) => deleteItem(...args),
  },
  ApiError: class ApiError extends Error {},
}));

const messages = {
  school_library: {
    lifecycle: {
      delete_section_title: "Delete from library",
      delete_section_help: "Soft-deletes this item.",
      delete_button: "Delete item",
      deleting: "Deleting…",
      delete_error: "Could not delete this item.",
    },
  },
};

describe("LibraryItemDeletePanel (T-064)", () => {
  beforeEach(() => {
    push.mockReset();
    deleteItem.mockReset();
    deleteItem.mockResolvedValue({ id: "item-1" });
  });

  it("hides when caller cannot delete", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <NextIntlClientProvider locale="en" messages={messages}>
          <LibraryItemDeletePanel itemId="item-1" libraryHref="/teacher/library" canDelete={false} />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("button", { name: /delete item/i })).not.toBeInTheDocument();
  });

  it("deletes item and redirects", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <NextIntlClientProvider locale="en" messages={messages}>
          <LibraryItemDeletePanel itemId="item-1" libraryHref="/teacher/library" canDelete />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /delete item/i }));

    await waitFor(() => {
      expect(deleteItem).toHaveBeenCalledWith("test-token", "item-1");
      expect(push).toHaveBeenCalledWith("/teacher/library");
    });
  });
});
