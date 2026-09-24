"use client";

import { MicIcon, SquareIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  isRecording: boolean;
  disabled?: boolean;
  permissionDenied?: boolean;
  startLabel: string;
  stopLabel: string;
  permissionDeniedLabel: string;
  onToggle: () => void;
};

/** Mic button + red pulse while recording (T-155). */
export function VoiceRecorder({
  isRecording,
  disabled,
  permissionDenied,
  startLabel,
  stopLabel,
  permissionDeniedLabel,
  onToggle,
}: Props) {
  const label = permissionDenied
    ? permissionDeniedLabel
    : isRecording
      ? stopLabel
      : startLabel;

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      disabled={disabled || permissionDenied}
      aria-label={label}
      title={label}
      aria-pressed={isRecording}
      data-testid="hybrid-mic-button"
      data-recording={isRecording ? "true" : "false"}
      onClick={onToggle}
      className={cn(
        "relative shrink-0",
        isRecording && "text-red-600 hover:bg-red-50 hover:text-red-700"
      )}
    >
      {isRecording ? (
        <>
          <span
            className="absolute inset-0 animate-ping rounded-full bg-red-400/40"
            aria-hidden="true"
            data-testid="hybrid-mic-pulse"
          />
          <SquareIcon className="relative size-5 fill-current" aria-hidden="true" />
        </>
      ) : (
        <MicIcon className="size-5" aria-hidden="true" />
      )}
    </Button>
  );
}
