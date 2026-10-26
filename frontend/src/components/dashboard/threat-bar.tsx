import Link from "next/link";

import { SEVERITY_COLOR } from "@/components/severity";
import { capitalize } from "@/lib/utils";
import { SEVERITIES, type Severity } from "@/lib/types";

/**
 * The dashboard's signature element: open work, split by severity, as one wide bar.
 * Segment width is proportional to count, so the mix is readable at a glance.
 */
export function ThreatBar({
  counts,
  hrefFor,
}: {
  counts: Record<Severity, number>;
  /** When given, each severity in the legend links to a filtered list. */
  hrefFor?: (severity: Severity) => string;
}) {
  const total = SEVERITIES.reduce((sum, s) => sum + counts[s], 0);

  return (
    <div>
      <div
        className="flex h-4 w-full gap-1 overflow-hidden rounded-full"
        role="img"
        aria-label={
          total === 0
            ? "No open incidents"
            : SEVERITIES.map((s) => `${counts[s]} ${s}`).join(", ")
        }
      >
        {total === 0 ? (
          <span className="h-full w-full rounded-full bg-secondary" />
        ) : (
          SEVERITIES.filter((s) => counts[s] > 0).map((s) => (
            <span
              key={s}
              className="h-full rounded-full"
              style={{ flexGrow: counts[s], background: SEVERITY_COLOR[s] }}
            />
          ))
        )}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {SEVERITIES.map((s) => (
          <div key={s} className="flex items-baseline gap-2">
            <dt className="flex items-center gap-2 text-muted-foreground">
              <span aria-hidden className="size-2 rounded-full" style={{ background: SEVERITY_COLOR[s] }} />
              {hrefFor ? (
                <Link href={hrefFor(s)} className="hover:text-foreground hover:underline">
                  {capitalize(s)}
                </Link>
              ) : (
                capitalize(s)
              )}
            </dt>
            <dd className="text-lg font-semibold">{counts[s]}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
