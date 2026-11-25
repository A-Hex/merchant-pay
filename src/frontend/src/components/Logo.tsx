import { cn } from "@/lib/utils";

/**
 * CEO-Pay mark: an open "C" (collections) with a growth arrow breaking out of it (decisions upward).
 * Drawn with theme colours, so it follows light/dark mode; `inverted` for dark brand panels.
 */
export function LogoMark({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  const ink = inverted ? "#0a0a0a" : "var(--primary-foreground)";
  return (
    <svg viewBox="0 0 32 32" role="img" aria-label="CEO-Pay"
      className={cn("shrink-0", inverted ? "text-white" : "text-primary", className)}>
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <path d="M21.9 10.1A8.4 8.4 0 1 0 21.9 21.9" fill="none" stroke={ink} strokeWidth="3" strokeLinecap="round" />
      <path d="M12.8 19.2 20.6 11.4M15.6 11.2h5.2v5.2" fill="none" stroke={ink} strokeWidth="2.4"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Mark + wordmark, e.g. for headers. */
export function Logo({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className="size-8" inverted={inverted} />
      <span className={cn("text-sm font-semibold tracking-tight", inverted && "text-white")}>
        CEO<span className={inverted ? "text-white/60" : "text-muted-foreground"}>-Pay</span>
      </span>
    </span>
  );
}
