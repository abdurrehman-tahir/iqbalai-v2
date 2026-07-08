import { cn } from "@/lib/utils";

type LogoSize = "sm" | "md" | "lg" | "xl";

interface IqbalLogoProps {
  /** Preset lockup size. */
  size?: LogoSize;
  /** Hide the "IQBAL AI" wordmark and render the leaf mark only. */
  markOnly?: boolean;
  /** Translated tagline shown under the wordmark (omit to hide it). */
  tagline?: string;
  /** Render the wordmark in white (for use on the dark top bar). */
  inverted?: boolean;
  className?: string;
}

const MARK_SIZE: Record<LogoSize, string> = {
  sm: "size-8",
  md: "size-9",
  lg: "size-12",
  xl: "size-16",
};

const WORDMARK_SIZE: Record<LogoSize, string> = {
  sm: "text-lg",
  md: "text-2xl",
  lg: "text-3xl",
  xl: "text-5xl",
};

/**
 * IqbalAI brand lockup — a leafed-eagle mark with a star accent plus the
 * "IQBAL AI" wordmark. The mark is a self-contained SVG (no external asset)
 * so it stays crisp at any size and carries the green brand gradient.
 */
export function IqbalLogo({
  size = "md",
  markOnly = false,
  tagline,
  inverted = false,
  className,
}: IqbalLogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className={MARK_SIZE[size]} />
      {!markOnly && (
        <span className="flex flex-col leading-none">
          <span className={cn("font-extrabold tracking-tight", WORDMARK_SIZE[size])}>
            <span className={inverted ? "text-white" : "text-gray-800"}>IQBAL</span>{" "}
            <span className="text-brand-600">AI</span>
          </span>
          {tagline && (
            <span
              className={cn(
                "mt-1 text-[0.6rem] font-medium tracking-wide",
                inverted ? "text-brand-200" : "text-brand-700/70"
              )}
            >
              {tagline}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      role="img"
      aria-label="IqbalAI"
      className={cn("shrink-0", className)}
    >
      <defs>
        <linearGradient
          id="iqbal-leaf"
          x1="8"
          y1="6"
          x2="40"
          y2="44"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#7BC043" />
          <stop offset="0.55" stopColor="#3FA34D" />
          <stop offset="1" stopColor="#1E7B3A" />
        </linearGradient>
      </defs>
      {/* Leaf / eagle body sweeping upward */}
      <path
        d="M9 39c-2-11 3-22 14-27 4.4-2 9.6-3 15-3-1.2 4.8-3.7 8.4-7.4 10.7 2.6.2 5-.3 7.4-1.4-1.6 5.2-5 8.9-9.8 10.8 1.8.4 3.7.3 5.6-.2-3 5.6-8.4 8.9-15 9.3l-4.2.6C13.7 41 11 40.4 9 39Z"
        fill="url(#iqbal-leaf)"
      />
      {/* Central vein */}
      <path
        d="M13 38c6-7 12.5-12.4 20-16.5"
        stroke="#ffffff"
        strokeOpacity="0.6"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      {/* Star accent */}
      <path
        d="M35.5 5.5l1.15 2.55L39.5 9l-2.35 1.2L35.5 13l-1.15-2.8L32 9l2.35-.95L35.5 5.5Z"
        fill="#2FA84F"
      />
    </svg>
  );
}
