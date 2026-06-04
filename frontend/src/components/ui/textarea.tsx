import { cn } from "@/lib/utils";
import { forwardRef } from "react";

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-gray-300 bg-white px-3 py-2",
        "text-sm text-gray-900 placeholder:text-gray-400 resize-y",
        "focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 focus:border-brand-600",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
