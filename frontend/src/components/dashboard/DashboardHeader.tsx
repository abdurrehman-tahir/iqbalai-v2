import { cn } from "@/lib/utils";

interface DashboardHeaderProps {
  title: string;
  subtitle?: string;
  /** Optional actions / links rendered on the trailing side (desktop) or below (mobile). */
  actions?: React.ReactNode;
  /** Extra content rendered under the title row (e.g. status pills, quick links). */
  children?: React.ReactNode;
  className?: string;
}

/**
 * Branded page hero shared across the role dashboards — a soft green gradient
 * card with a leading accent bar, matching the login surface's visual language.
 */
export function DashboardHeader({
  title,
  subtitle,
  actions,
  children,
  className,
}: DashboardHeaderProps) {
  return (
    <header
      className={cn(
        "relative overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-br from-brand-50 to-white p-6 sm:p-7",
        className
      )}
    >
      {/* Leading brand accent bar. */}
      <span aria-hidden="true" className="absolute inset-y-0 start-0 w-1.5 bg-brand-500" />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">{title}</h2>
          {subtitle && <p className="text-sm text-gray-600">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </header>
  );
}
