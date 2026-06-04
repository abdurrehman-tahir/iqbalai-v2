import { cn } from "@/lib/utils";

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
}

export function Label({ className, required, children, ...props }: LabelProps) {
  return (
    <label
      className={cn(
        "block text-sm font-medium text-gray-700 mb-1",
        className,
      )}
      {...props}
    >
      {children}
      {required && (
        <span className="ms-1 text-red-500" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}
