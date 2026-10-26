"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";

import { Pagination } from "@/components/pagination";
import { AlertStatusBadge, SeverityBadge } from "@/components/severity";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDebounced } from "@/hooks/use-debounced";
import { useAlerts, useRules } from "@/hooks/use-security";
import { ALERT_STATUSES, SEVERITIES, type AlertStatus, type Severity } from "@/lib/types";
import { capitalize, formatDateTime } from "@/lib/utils";

const ALL = "all";
const PAGE_SIZE = 25;

function pick<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined;
}

/**
 * Filters can arrive in the URL (e.g. /alerts?severity=high from the dashboard).
 * The view is keyed by the query string, so following a new link always starts from
 * that link's filters, even though Next keeps visited pages mounted in the background.
 */
export default function AlertsPage() {
  const params = useSearchParams();
  const status = params.get("status");
  return (
    <AlertsView
      key={params.toString()}
      initial={{
        severity: pick(params.get("severity"), SEVERITIES) ?? ALL,
        status: status === "all" ? ALL : (pick(status, ALERT_STATUSES) ?? "open"),
        rule: params.get("rule_id") ?? ALL,
        srcIp: params.get("src_ip") ?? undefined,
        uploadId: params.get("upload_id") ?? undefined,
      }}
    />
  );
}

interface Initial {
  severity: Severity | typeof ALL;
  status: AlertStatus | typeof ALL;
  rule: string;
  srcIp?: string;
  uploadId?: string;
}

function AlertsView({ initial }: { initial: Initial }) {
  const router = useRouter();
  const [severity, setSeverity] = useState(initial.severity);
  const [status, setStatus] = useState(initial.status);
  const [rule, setRule] = useState<string>(initial.rule);
  const [srcIp, setSrcIp] = useState(initial.srcIp);
  const [uploadId, setUploadId] = useState(initial.uploadId);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  const rules = useRules();

  const { data, error, isPending, isPlaceholderData, refetch } = useAlerts({
    severity: severity === ALL ? undefined : severity,
    status: status === ALL ? undefined : status,
    rule_id: rule === ALL ? undefined : rule,
    src_ip: srcIp,
    upload_id: uploadId,
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const filtered =
    severity !== ALL || status !== ALL || rule !== ALL || q !== "" || !!srcIp || !!uploadId;
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Findings from detection rules. Each one links to the log events that triggered it."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_auto_auto_auto]">
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
          <Input
            type="search"
            placeholder="Search titles and accounts"
            aria-label="Search alerts"
            className="pl-9"
            value={search}
            maxLength={100}
            onChange={(e) => reset(setSearch)(e.target.value)}
          />
        </div>
        <Select value={status} onValueChange={(v) => reset(setStatus)(v as AlertStatus | typeof ALL)}>
          <SelectTrigger className="lg:w-44" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {ALERT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {capitalize(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={severity} onValueChange={(v) => reset(setSeverity)(v as Severity | typeof ALL)}>
          <SelectTrigger className="lg:w-40" aria-label="Filter by severity">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All severities</SelectItem>
            {SEVERITIES.map((s) => (
              <SelectItem key={s} value={s}>
                {capitalize(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={rule} onValueChange={reset(setRule)}>
          <SelectTrigger className="lg:w-52" aria-label="Filter by rule">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All rules</SelectItem>
            {rules.data?.map((r) => (
              <SelectItem key={r.id} value={r.id}>
                {r.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {(srcIp || uploadId) && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Also filtered by</span>
          {srcIp && (
            <FilterChip label={`source ${srcIp}`} onClear={() => { setSrcIp(undefined); setPage(1); }} />
          )}
          {uploadId && (
            <FilterChip label="one upload" onClear={() => { setUploadId(undefined); setPage(1); }} />
          )}
        </div>
      )}

      <div className="rounded-lg border bg-panel">
        {error ? (
          <div className="p-4">
            <ErrorState error={error} onRetry={() => refetch()} />
          </div>
        ) : isPending ? (
          <div className="flex flex-col gap-2 p-4" aria-busy>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            title={filtered ? "No alerts match these filters" : "No alerts yet"}
            description={
              filtered
                ? "Try another status or rule, or clear the search."
                : "Upload a security log and the detection rules will flag anything suspicious here."
            }
            action={
              filtered ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSeverity(ALL);
                    setStatus(ALL);
                    setRule(ALL);
                    setSrcIp(undefined);
                    setUploadId(undefined);
                    setSearch("");
                    setPage(1);
                  }}
                >
                  Clear filters
                </Button>
              ) : (
                <Button size="sm" onClick={() => router.push("/uploads")}>
                  Upload a log
                </Button>
              )
            }
          />
        ) : (
          <Table className={isPlaceholderData ? "opacity-60" : undefined}>
            <TableHeader>
              <TableRow>
                <TableHead className="w-28">Severity</TableHead>
                <TableHead>Alert</TableHead>
                <TableHead className="hidden w-40 md:table-cell">Source</TableHead>
                <TableHead className="hidden w-20 text-right lg:table-cell">Events</TableHead>
                <TableHead className="hidden w-40 lg:table-cell">First seen</TableHead>
                <TableHead className="w-40">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((a) => (
                <TableRow
                  key={a.id}
                  className="cursor-pointer hover:bg-secondary/50"
                  onClick={() => router.push(`/alerts/${a.id}`)}
                >
                  <TableCell>
                    <SeverityBadge severity={a.severity} />
                  </TableCell>
                  <TableCell>
                    <a
                      href={`/alerts/${a.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        router.push(`/alerts/${a.id}`);
                      }}
                      className="font-medium hover:underline"
                    >
                      {a.title}
                    </a>
                    <span className="block text-sm text-muted-foreground">
                      {a.rule_id} {a.rule_name}
                    </span>
                  </TableCell>
                  <TableCell className="hidden font-mono text-sm md:table-cell">
                    {a.src_ip ?? "—"}
                  </TableCell>
                  <TableCell className="hidden text-right lg:table-cell">{a.event_count}</TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">
                    {formatDateTime(a.first_seen)}
                  </TableCell>
                  <TableCell>
                    <AlertStatusBadge status={a.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
      </div>
    </>
  );
}

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border bg-secondary py-0.5 pl-3 pr-1">
      {label}
      <button
        type="button"
        onClick={onClear}
        aria-label={`Remove filter: ${label}`}
        className="rounded-full p-0.5 text-muted-foreground hover:bg-ink hover:text-foreground"
      >
        <X className="size-3.5" />
      </button>
    </span>
  );
}
