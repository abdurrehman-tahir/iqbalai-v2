import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../../../messages/en/common.json";
import { LiveFeedbackPanel, StuckNudge } from "../LiveFeedbackPanel";

function wrap(ui: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("LiveFeedbackPanel", () => {
  it("stays hidden until panel_visible", () => {
    const { container } = render(
      wrap(
        <LiveFeedbackPanel
          sessionId="s1"
          metrics={{ panel_visible: false, time_on_topic_seconds: 30 }}
          collapsed={false}
          onToggleCollapsed={() => undefined}
        />,
      ),
    );
    expect(container.querySelector('[data-testid="live-feedback-panel"]')).toBeNull();
  });

  it("shows available metrics only", () => {
    render(
      wrap(
        <LiveFeedbackPanel
          sessionId="s1"
          metrics={{
            panel_visible: true,
            time_on_topic_seconds: 150,
            questions_asked_this_session: 2,
            mastery_estimate: null,
            daily_goal_status: null,
          }}
          collapsed={false}
          onToggleCollapsed={() => undefined}
        />,
      ),
    );
    expect(screen.getByTestId("live-feedback-panel")).toBeInTheDocument();
    expect(screen.getByTestId("live-feedback-questions")).toHaveTextContent("2");
    expect(screen.queryByText(/mastery/i)).toBeNull();
  });

  it("collapses on toggle", () => {
    const onToggle = vi.fn();
    render(
      wrap(
        <LiveFeedbackPanel
          sessionId="s1"
          metrics={{ panel_visible: true, time_on_topic_seconds: 200 }}
          collapsed={false}
          onToggleCollapsed={onToggle}
        />,
      ),
    );
    fireEvent.click(screen.getByTestId("live-feedback-collapse"));
    expect(onToggle).toHaveBeenCalled();
  });
});

describe("StuckNudge", () => {
  it("renders once and dismisses", () => {
    const onDismiss = vi.fn();
    render(
      wrap(
        <StuckNudge
          open
          onDismiss={onDismiss}
          onRephrase={() => undefined}
          onListConcepts={() => undefined}
          onSwitchVoice={() => undefined}
        />,
      ),
    );
    expect(screen.getByTestId("stuck-nudge")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("stuck-nudge-dismiss"));
    expect(onDismiss).toHaveBeenCalled();
  });
});
