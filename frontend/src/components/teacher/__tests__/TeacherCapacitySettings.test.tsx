import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { TeacherCapacitySettings } from "../TeacherCapacitySettings";

const updateCapacity = vi.fn();

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

vi.mock("@/lib/api", () => ({
  teacherOnboardingApi: {
    updateCapacity: (...args: unknown[]) => updateCapacity(...args),
  },
  ApiError: class ApiError extends Error {},
}));

const messages = {
  teacher: {
    capacity: {
      title: "Teaching capacity",
      subtitle: "Maximum grade-subject assignments you can hold.",
      field_label: "Capacity",
      field_help: "Between {min} and {max}. You have {count} assignments now.",
      below_assignments_warning:
        "Capacity {capacity} is below your {count} current assignments. New assignments are blocked until you are under cap.",
      currently_below_assignments:
        "Your capacity is below your {count} current assignments.",
      admin_override_help:
        "School Admins can override capacity when assigning offerings.",
      save: "Save capacity",
      saving: "Saving…",
      saved: "Capacity saved.",
      error_generic: "Could not save capacity.",
    },
  },
};

function renderPanel(onboarding = baseOnboarding) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={messages}>
        <TeacherCapacitySettings onboarding={onboarding} />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

const baseOnboarding = {
  state: "ready_to_teach" as const,
  profile_complete: true,
  ready_to_teach: true,
  assignment_count: 3,
  can_create_content: true,
  teacher_capacity: 5,
  capacity_below_assignments: false,
  profile: null,
};

describe("TeacherCapacitySettings (T-062)", () => {
  beforeEach(() => {
    updateCapacity.mockReset();
    updateCapacity.mockResolvedValue({
      teacher_capacity: 8,
      assignment_count: 3,
      capacity_below_assignments: false,
    });
  });

  it("submits valid capacity update", async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText(/capacity/i), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: /save capacity/i }));

    await waitFor(() => {
      expect(updateCapacity).toHaveBeenCalledWith("test-token", { teacher_capacity: 8 });
    });
    expect(await screen.findByText(/capacity saved/i)).toBeInTheDocument();
  });

  it("shows warning when lowering below assignment count", () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText(/capacity/i), { target: { value: "2" } });
    expect(screen.getByRole("status")).toHaveTextContent(/below your 3 current assignments/i);
  });
});
