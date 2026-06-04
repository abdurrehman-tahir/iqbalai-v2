import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AlertCircleIcon } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  description: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function ErrorState({
  title,
  description,
  onRetry,
  retryLabel = "Try again",
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className,
      )}
    >
      <div className="rounded-full bg-red-50 p-4 mb-4">
        <AlertCircleIcon className="size-8 text-red-500" aria-hidden="true" />
      </div>
      {title && (
        <h3 className="text-base font-semibold text-gray-900 mb-1">{title}</h3>
      )}
      <p className="text-sm text-gray-500 max-w-sm mb-6">{description}</p>
      {onRetry && (
        <Button variant="outline" size="md" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
