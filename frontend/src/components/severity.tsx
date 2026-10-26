import { cn, capitalize } from "@/lib/utils";
import type { AlertStatus, IncidentStatus, Severity } from "@/lib/types";

/*
  Severity is the product's color system. The dot + label pairing means color is
  never the only signal (accessible for color-blind users).
*/
export const SEVERITY_COLOR: Record<Severity, string> = {
  low: "var(--sev-low)",
  medium: "var(--sev-medium)",
  high: "var(--sev-high)",
  critical: "var(--sev-critical)",
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-medium",
        className,
      )}
      style={{ color: SEVERITY_COLOR[severity] }}
    >
      <span
        aria-hidden
        className={cn("rounded-full", severity === "critical" ? "size-2.5" : "size-2")}
        style={{ background: SEVERITY_COLOR[severity] }}
      />
      {capitalize(severity)}
    </span>
  );
}

const STATUS_STYLE: Record<IncidentStatus, string> = {
  open: "border-foreground/40 text-foreground",
  investigating: "border-primary/60 text-primary",
  contained: "border-sev-medium/50 text-sev-medium",
  resolved: "border-sev-low/50 text-sev-low",
  closed: "border-border text-muted-foreground",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        STATUS_STYLE[status],
      )}
    >
      {capitalize(status)}
    </span>
  );
}

const ALERT_STATUS_STYLE: Record<AlertStatus, string> = {
  open: "border-foreground/40 text-foreground",
  acknowledged: "border-primary/60 text-primary",
  dismissed: "border-border text-muted-foreground",
  escalated: "border-sev-high/50 text-sev-high",
};

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        ALERT_STATUS_STYLE[status],
      )}
    >
      {status === "escalated" ? "Escalated to incident" : capitalize(status)}
    </span>
  );
}
