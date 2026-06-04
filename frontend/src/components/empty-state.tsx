import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { InboxIcon } from "lucide-react";
import Link from "next/link";
// Link import kept for href variant — Button import for onClick variant

interface EmptyStateProps {
  title: string;
  description: string;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = InboxIcon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className,
      )}
    >
      <div className="rounded-full bg-gray-100 p-4 mb-4">
        <Icon className="size-8 text-gray-400" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 max-w-sm mb-6">{description}</p>
      {action &&
        (action.href ? (
          <Link
            href={action.href}
            className="inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors h-10 px-4 text-sm bg-brand-600 text-white hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-600"
          >
            {action.label}
          </Link>
        ) : (
          <Button variant="primary" size="md" onClick={action.onClick}>
            {action.label}
          </Button>
        ))}
    </div>
  );
}
