import { cn } from "@/lib/utils";
import { forwardRef } from "react";

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2",
        "text-sm text-gray-900 placeholder:text-gray-400",
        "focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 focus:border-brand-600",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
