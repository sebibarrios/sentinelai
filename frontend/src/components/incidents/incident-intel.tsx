"use client";

import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { AiList, AiPanel } from "@/components/ai-panel";
import { SeverityBadge } from "@/components/severity";
import { Skeleton } from "@/components/ui/table";
import {
  useAiStatus,
  useAlerts,
  useGenerateIncidentReport,
  useIncidentReport,
} from "@/hooks/use-security";
import { formatDateTime } from "@/lib/utils";

/** Alerts promoted into this incident: the verified evidence it rests on. */
export function LinkedAlerts({ incidentId }: { incidentId: string }) {
  const { data, isPending } = useAlerts({ incident_id: incidentId, page: 1, page_size: 50 });
  if (isPending) return <Skeleton className="h-24 w-full" />;
  if (!data || data.items.length === 0) return null;

  return (
    <section className="rounded-lg border bg-panel" aria-labelledby="linked-alerts">
      <h2 id="linked-alerts" className="flex items-center gap-2 px-5 pb-2 pt-5 font-medium">
        <ShieldCheck className="size-4 text-sev-low" aria-hidden />
        Linked alerts <span className="font-normal text-muted-foreground">({data.total})</span>
      </h2>
      <ul>
        {data.items.map((a) => (
          <li key={a.id} className="border-t">
            <Link
              href={`/alerts/${a.id}`}
              className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-secondary/50"
            >
              <SeverityBadge severity={a.severity} className="w-20 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{a.title}</span>
                <span className="text-sm text-muted-foreground">
                  {a.rule_id} {a.rule_name}, {a.event_count} events from{" "}
                  {formatDateTime(a.first_seen)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function IncidentAiReport({ incidentId, canEdit }: { incidentId: string; canEdit: boolean }) {
  const report = useIncidentReport(incidentId);
  const generate = useGenerateIncidentReport(incidentId);
  const ai = useAiStatus();
  const r = report.data?.output;

  return (
    <AiPanel
      title="AI incident report"
      description="Draft a structured report from this incident's alerts and investigation notes."
      analysis={report.data}
      aiEnabled={ai.data?.enabled}
      canRequest={canEdit}
      generating={generate.isPending}
      error={generate.error}
      onGenerate={() => generate.mutate()}
      generateLabel="Draft report"
    >
      {r && (
        <div className="flex flex-col gap-5">
          <div>
            <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">Executive summary</h3>
            <p className="max-w-[72ch]">{r.executive_summary}</p>
          </div>
          {r.timeline.length > 0 && (
            <div>
              <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">Timeline</h3>
              <ol className="flex flex-col gap-1.5">
                {r.timeline.map((t, i) => (
                  <li key={i} className="grid grid-cols-[minmax(0,11rem)_1fr] gap-3">
                    <span className="font-mono text-xs text-muted-foreground">{t.time}</span>
                    <span>{t.event}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div>
            <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">Impact assessment</h3>
            <p className="max-w-[72ch]">{r.impact_assessment}</p>
          </div>
          {(r.indicators.length > 0 || !!r.ungrounded_indicators_removed) && (
            <div>
              <h3 className="mb-1.5 text-sm font-medium text-muted-foreground">
                Indicators (each checked against the incident data)
              </h3>
              {r.indicators.length > 0 ? (
                <ul className="flex flex-col gap-1">
                  {r.indicators.map((ind, i) => (
                    <li key={i}>
                      <span className="font-mono text-sm">{ind.value}</span>{" "}
                      <span className="text-muted-foreground">
                        {ind.type}, {ind.context}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">None that appear in the incident data.</p>
              )}
              {/* Always shown when something was dropped, even if nothing survived. */}
              {!!r.ungrounded_indicators_removed && (
                <p className="mt-2 text-sm text-sev-medium">
                  {r.ungrounded_indicators_removed} indicator
                  {r.ungrounded_indicators_removed === 1 ? " was" : "s were"} removed because{" "}
                  {r.ungrounded_indicators_removed === 1 ? "it doesn't" : "they don't"} appear in the
                  incident data.
                </p>
              )}
            </div>
          )}
          <AiList title="Affected accounts" items={r.affected_accounts} />
          <AiList title="Containment steps" items={r.containment_steps} />
          <AiList title="Recommendations" items={r.recommendations} />
          <AiList title="Open questions" items={r.open_questions} />
          <AiList title="Caveats" items={r.caveats} />
        </div>
      )}
    </AiPanel>
  );
}
