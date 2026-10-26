"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { AiList, AiPanel } from "@/components/ai-panel";
import { EventsTable } from "@/components/evidence-table";
import { AlertStatusBadge, SeverityBadge } from "@/components/severity";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/table";
import { useCan } from "@/hooks/use-auth";
import {
  useAiStatus,
  useAlert,
  useExplainAlert,
  usePromoteAlert,
  useUpdateAlertStatus,
} from "@/hooks/use-security";
import { ApiError } from "@/lib/api";
import type { AlertDetail, AlertStatus } from "@/lib/types";
import { capitalize, formatDateTime } from "@/lib/utils";

export default function AlertPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isPending, refetch } = useAlert(id);

  return (
    <>
      <Link
        href="/alerts"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Alerts
      </Link>
      {error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <div className="flex flex-col gap-4" aria-busy>
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <AlertView alert={data} />
      )}
    </>
  );
}

function label(key: string) {
  return capitalize(key.replaceAll("_", " "));
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function AlertView({ alert }: { alert: AlertDetail }) {
  const router = useRouter();
  const canEdit = useCan("analyst");
  const status = useUpdateAlertStatus(alert.id);
  const promote = usePromoteAlert(alert.id);
  const explain = useExplainAlert(alert.id);
  const ai = useAiStatus();
  const linked = alert.incident_id !== null;
  const ex = alert.ai_analysis?.output;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">
            {alert.rule_id} {alert.rule_name}
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">{alert.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <SeverityBadge severity={alert.severity} />
            <AlertStatusBadge status={alert.status} />
          </div>
        </div>
        {canEdit && (
          <div className="flex flex-wrap items-center gap-2">
            {!linked && (
              <Select
                value={alert.status}
                disabled={status.isPending}
                onValueChange={(v) =>
                  status.mutate(v as AlertStatus, {
                    onSuccess: () => toast.success(`Alert marked ${v}`),
                    onError: (e) =>
                      toast.error(e instanceof ApiError ? e.displayMessage : "Update failed"),
                  })
                }
              >
                <SelectTrigger className="w-40" aria-label="Alert status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(["open", "acknowledged", "dismissed"] as const).map((s) => (
                    <SelectItem key={s} value={s}>
                      {capitalize(s)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {linked ? (
              <Button asChild variant="outline">
                <Link href={`/incidents/${alert.incident_id}`}>Open linked incident</Link>
              </Button>
            ) : (
              <Button
                disabled={promote.isPending}
                onClick={() =>
                  promote.mutate(undefined, {
                    onSuccess: (r) => {
                      toast.success(`Created ${r.reference}`);
                      router.push(`/incidents/${r.incident_id}`);
                    },
                    onError: (e) =>
                      toast.error(e instanceof ApiError ? e.displayMessage : "Couldn't promote"),
                  })
                }
              >
                {promote.isPending ? "Creating incident…" : "Promote to incident"}
              </Button>
            )}
          </div>
        )}
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="min-w-0 rounded-lg border bg-panel p-5" aria-labelledby="verified-heading">
          <h2 id="verified-heading" className="flex items-center gap-2 font-medium">
            <ShieldCheck className="size-4 text-sev-low" aria-hidden />
            Verified finding
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Produced by a deterministic rule from the log events below. Rule: {alert.rule_description}.
          </p>
          <dl className="mt-4 grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)] gap-x-4 gap-y-2">
            <dt className="text-muted-foreground">First seen</dt>
            <dd>{formatDateTime(alert.first_seen)}</dd>
            <dt className="text-muted-foreground">Last seen</dt>
            <dd>{formatDateTime(alert.last_seen)}</dd>
            <dt className="text-muted-foreground">Matching events</dt>
            <dd>{alert.event_count}</dd>
            {alert.src_ip && (
              <>
                <dt className="text-muted-foreground">Source IP</dt>
                <dd className="font-mono text-sm">{alert.src_ip}</dd>
              </>
            )}
            {alert.username && (
              <>
                <dt className="text-muted-foreground">Account</dt>
                <dd>{alert.username}</dd>
              </>
            )}
            {Object.entries(alert.details).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{label(k)}</dt>
                <dd className="break-words">{formatValue(v)}</dd>
              </div>
            ))}
          </dl>
        </section>

        <AiPanel
          title="AI analyst"
          description="Ask the AI analyst to explain this alert and suggest what to check next."
          analysis={alert.ai_analysis}
          aiEnabled={ai.data?.enabled}
          canRequest={canEdit}
          generating={explain.isPending}
          error={explain.error}
          onGenerate={() => explain.mutate()}
          generateLabel="Explain this alert"
        >
          {ex && (
            <div className="flex flex-col gap-4">
              <p className="text-md">{ex.summary}</p>
              <p className="text-muted-foreground">{ex.explanation}</p>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                <span>
                  <span className="text-muted-foreground">Suggested severity:</span>{" "}
                  {capitalize(ex.recommended_severity)}
                </span>
                <span>
                  <span className="text-muted-foreground">Confidence:</span> {capitalize(ex.confidence)}
                </span>
              </div>
              {ex.investigation_steps.length > 0 && (
                <div>
                  <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">
                    Suggested investigation steps
                  </h3>
                  <ol className="flex list-decimal flex-col gap-2 pl-5">
                    {ex.investigation_steps.map((s, i) => (
                      <li key={i}>
                        {s.step}
                        <span className="block text-sm text-muted-foreground">{s.rationale}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              <AiList title="Consistent with" items={ex.likely_tactics} />
              <AiList title="What this doesn't establish" items={ex.caveats} />
            </div>
          )}
        </AiPanel>
      </div>

      <section className="rounded-lg border bg-panel" aria-labelledby="evidence-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pb-2 pt-5">
          <h2 id="evidence-heading" className="font-medium">
            Evidence <span className="font-normal text-muted-foreground">({alert.evidence.length})</span>
          </h2>
          {alert.evidence_truncated && (
            <p className="text-sm text-muted-foreground">
              Showing the first {alert.evidence.length} of {alert.event_count} events.
            </p>
          )}
        </div>
        <EventsTable events={alert.evidence} />
      </section>
    </div>
  );
}
