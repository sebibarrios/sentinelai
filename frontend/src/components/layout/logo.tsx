import { cn } from "@/lib/utils";

/** Mark: a watch arc over a dot — a sentinel's field of view. */
export function Logo({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
        <path
          d="M3.5 15a8.5 8.5 0 0 1 17 0"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <path
          d="M7.5 15a4.5 4.5 0 0 1 9 0"
          fill="none"
          stroke="var(--accent)"
          strokeOpacity="0.55"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <circle cx="12" cy="15" r="1.9" fill="var(--fg)" />
      </svg>
      <span className={cn("font-semibold tracking-tight text-foreground", compact ? "text-md" : "text-lg")}>
        Sentinel<span className="font-normal text-muted-foreground">AI</span>
      </span>
    </span>
  );
}
