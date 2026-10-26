"use client";

import { useState } from "react";
import Link from "next/link";

import { AlertTimeline } from "@/components/dashboard/alert-timeline";
import { StatusChart } from "@/components/dashboard/status-chart";
import { ThreatBar } from "@/components/dashboard/threat-bar";
import { AlertStatusBadge, SeverityBadge, StatusBadge } from "@/components/severity";
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
  const [range, setRange] = useState<DashboardSummary["range"]>("24h");
  const { data, error, isPending, refetch } = useDashboard(range);
  const rangeLabel = RANGES.find((r) => r.value === range)?.label;

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
          <section className="rounded-lg border bg-panel p-6" aria-labelledby="open-alerts">
            <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <h2 id="open-alerts" className="text-md font-medium">
                <span className="text-xl font-semibold">{data.open_alerts}</span>{" "}
                <span className="text-muted-foreground">open alerts by severity</span>
              </h2>
              <p className="text-sm text-muted-foreground">
                Last {rangeLabel}: {data.events_in_range.toLocaleString()} events analyzed,{" "}
                {data.alerts_in_range} alerts, {data.incidents_in_range} incidents opened
              </p>
            </div>
            <ThreatBar counts={data.open_alerts_by_severity} />
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <section className="min-w-0 rounded-lg border bg-panel p-6 lg:col-span-2">
              <h2 className="mb-3 font-medium">Alerts over time</h2>
              {data.alerts_in_range === 0 ? (
                <EmptyState
                  title={`No alerts in the last ${rangeLabel}`}
                  description="Try a longer time range, or upload a log to analyze."
                />
              ) : (
                <AlertTimeline points={data.alert_timeline} hourly={range === "24h"} />
              )}
            </section>

            <section className="min-w-0 rounded-lg border bg-panel p-6">
              <h2 className="mb-3 font-medium">Top alerting sources</h2>
              {data.top_sources.length === 0 ? (
                <p className="text-muted-foreground">No alerting IPs in this range.</p>
              ) : (
                <ol className="flex flex-col">
                  {data.top_sources.map((s) => {
                    const max = data.top_sources[0].alerts;
                    return (
                      <li key={s.ip} className="border-t py-3 first:border-t-0 first:pt-0">
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate font-mono text-sm">{s.ip}</span>
                          <SeverityBadge severity={s.max_severity} />
                        </div>
                        <div className="mt-2 flex items-center gap-3">
                          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                            <span
                              className="block h-full rounded-full bg-primary/70"
                              style={{ width: `${(s.alerts / max) * 100}%` }}
                            />
                          </span>
                          <span className="w-16 text-right text-sm text-muted-foreground">
                            {s.alerts} alert{s.alerts === 1 ? "" : "s"}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section className="min-w-0 rounded-lg border bg-panel">
              <div className="flex items-center justify-between px-6 pb-2 pt-5">
                <h2 className="font-medium">Latest alerts</h2>
                <Button asChild variant="link" size="sm" className="px-0">
                  <Link href="/alerts">View all</Link>
                </Button>
              </div>
              {data.recent_alerts.length === 0 ? (
                <EmptyState
                  title="No alerts yet"
                  description="Upload a security log and detection rules will flag suspicious activity here."
                  action={
                    <Button asChild size="sm">
                      <Link href="/uploads">Upload a log</Link>
                    </Button>
                  }
                />
              ) : (
                <ul>
                  {data.recent_alerts.map((a) => (
                    <li key={a.id} className="border-t first:border-t-0">
                      <Link
                        href={`/alerts/${a.id}`}
                        className="flex items-center gap-4 px-6 py-3 transition-colors hover:bg-secondary/50"
                      >
                        <SeverityBadge severity={a.severity} className="w-20 shrink-0" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{a.title}</span>
                          <span className="text-sm text-muted-foreground">
                            {a.rule_name}, {formatRelative(a.first_seen)}
                          </span>
                        </span>
                        <span className="hidden sm:block">
                          <AlertStatusBadge status={a.status} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="min-w-0 rounded-lg border bg-panel">
              <div className="flex items-center justify-between px-6 pb-2 pt-5">
                <h2 className="font-medium">
                  Incidents{" "}
                  <span className="font-normal text-muted-foreground">({data.open_incidents} open)</span>
                </h2>
                <Button asChild variant="link" size="sm" className="px-0">
                  <Link href="/incidents">View all</Link>
                </Button>
              </div>
              <div className="px-6">
                <StatusChart counts={data.incidents_by_status} />
              </div>
              {data.recent_incidents.length > 0 && (
                <ul className="border-t">
                  {data.recent_incidents.slice(0, 3).map((inc) => (
                    <li key={inc.id} className="border-t first:border-t-0">
                      <Link
                        href={`/incidents/${inc.id}`}
                        className="flex items-center gap-4 px-6 py-3 transition-colors hover:bg-secondary/50"
                      >
                        <SeverityBadge severity={inc.severity} className="w-20 shrink-0" />
                        <span className="min-w-0 flex-1 truncate font-medium">{inc.title}</span>
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
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-80 lg:col-span-2" />
        <Skeleton className="h-80" />
      </div>
    </div>
  );
}
