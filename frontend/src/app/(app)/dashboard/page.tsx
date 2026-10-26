"use client";

import { useState } from "react";
import Link from "next/link";

import { StatusChart } from "@/components/dashboard/status-chart";
import { ThreatBar } from "@/components/dashboard/threat-bar";
import { SeverityBadge, StatusBadge } from "@/components/severity";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/table";
import { useDashboard } from "@/hooks/use-incidents";
import type { DashboardSummary } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

const RANGES: { value: DashboardSummary["range"]; label: string }[] = [
  { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
];

export default function DashboardPage() {
  const [range, setRange] = useState<DashboardSummary["range"]>("7d");
  const { data, error, isPending, refetch } = useDashboard(range);

  return (
    <>
      <PageHeader
        title="Dashboard"
        actions={
          <div role="group" aria-label="Time range" className="flex rounded-md border p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.value}
                onClick={() => setRange(r.value)}
                aria-pressed={range === r.value}
                className={cn(
                  "rounded-[5px] px-3 py-1 text-sm transition-colors",
                  range === r.value
                    ? "bg-secondary font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <DashboardSkeleton />
      ) : (
        <div className="flex flex-col gap-6">
          <section className="rounded-lg border bg-panel p-6" aria-labelledby="open-work">
            <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="open-work" className="text-md font-medium">
                <span className="text-xl font-semibold">{data.open_incidents}</span>{" "}
                <span className="text-muted-foreground">open incidents by severity</span>
              </h2>
              <p className="text-sm text-muted-foreground">
                {data.incidents_in_range} opened in the last {RANGES.find((r) => r.value === range)?.label}
              </p>
            </div>
            <ThreatBar counts={data.incidents_by_severity} />
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <section className="min-w-0 rounded-lg border bg-panel p-6 lg:col-span-2">
              <h2 className="mb-2 font-medium">All incidents by status</h2>
              <StatusChart counts={data.incidents_by_status} />
            </section>

            <section className="min-w-0 rounded-lg border bg-panel lg:col-span-3">
              <div className="flex items-center justify-between px-6 pb-2 pt-5">
                <h2 className="font-medium">Recent incidents</h2>
                <Button asChild variant="link" size="sm" className="px-0">
                  <Link href="/incidents">View all</Link>
                </Button>
              </div>
              {data.recent_incidents.length === 0 ? (
                <EmptyState
                  title="No incidents yet"
                  description="Incidents you open, or promote from alerts, will show up here."
                />
              ) : (
                <ul>
                  {data.recent_incidents.map((inc) => (
                    <li key={inc.id} className="border-t first:border-t-0">
                      <Link
                        href={`/incidents/${inc.id}`}
                        className="flex items-center gap-4 px-6 py-3 transition-colors hover:bg-secondary/50"
                      >
                        <SeverityBadge severity={inc.severity} className="w-20 shrink-0" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{inc.title}</span>
                          <span className="text-sm text-muted-foreground">
                            {inc.reference}, opened {formatRelative(inc.created_at)}
                          </span>
                        </span>
                        <StatusBadge status={inc.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      )}
    </>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy>
      <Skeleton className="h-40 w-full" />
      <div className="grid gap-6 lg:grid-cols-5">
        <Skeleton className="h-72 lg:col-span-2" />
        <Skeleton className="h-72 lg:col-span-3" />
      </div>
    </div>
  );
}
