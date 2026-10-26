"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";

import { NewIncidentDialog } from "@/components/incidents/incident-form-dialog";
import { SeverityBadge, StatusBadge } from "@/components/severity";
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
import { useCan } from "@/hooks/use-auth";
import { useDebounced } from "@/hooks/use-debounced";
import { useIncidents } from "@/hooks/use-incidents";
import { INCIDENT_STATUSES, SEVERITIES, type IncidentStatus, type Severity } from "@/lib/types";
import { capitalize, formatDateTime } from "@/lib/utils";

const ALL = "all";
const PAGE_SIZE = 20;

export default function IncidentsPage() {
  const router = useRouter();
  const canEdit = useCan("analyst");
  const [status, setStatus] = useState<IncidentStatus | typeof ALL>(ALL);
  const [severity, setSeverity] = useState<Severity | typeof ALL>(ALL);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());

  const { data, error, isPending, isPlaceholderData, refetch } = useIncidents({
    status: status === ALL ? undefined : status,
    severity: severity === ALL ? undefined : severity,
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const filtered = status !== ALL || severity !== ALL || q !== "";

  return (
    <>
      <PageHeader
        title="Incidents"
        description="Track investigations from first report to closure."
        actions={
          canEdit && (
            <NewIncidentDialog
              trigger={
                <Button>
                  <Plus /> New incident
                </Button>
              }
            />
          )
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
          <Input
            type="search"
            placeholder="Search titles and descriptions"
            aria-label="Search incidents"
            className="pl-9"
            value={search}
            maxLength={100}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v as IncidentStatus | typeof ALL);
            setPage(1);
          }}
        >
          <SelectTrigger className="sm:w-44" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {INCIDENT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {capitalize(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={severity}
          onValueChange={(v) => {
            setSeverity(v as Severity | typeof ALL);
            setPage(1);
          }}
        >
          <SelectTrigger className="sm:w-44" aria-label="Filter by severity">
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
      </div>

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
            title={filtered ? "No incidents match these filters" : "No incidents yet"}
            description={
              filtered
                ? "Try a different search term, or clear the status and severity filters."
                : canEdit
                  ? "Open an incident when something needs investigating."
                  : "Incidents opened by analysts will appear here."
            }
          />
        ) : (
          <Table className={isPlaceholderData ? "opacity-60" : undefined}>
            <TableHeader>
              <TableRow>
                <TableHead className="hidden w-24 sm:table-cell">ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="w-28">Severity</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="hidden w-44 md:table-cell">Assignee</TableHead>
                <TableHead className="hidden w-40 lg:table-cell">Opened</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((inc) => (
                <TableRow
                  key={inc.id}
                  className="cursor-pointer hover:bg-secondary/50"
                  onClick={() => router.push(`/incidents/${inc.id}`)}
                >
                  <TableCell className="hidden text-muted-foreground sm:table-cell">{inc.reference}</TableCell>
                  <TableCell>
                    {/* Real link for keyboard and screen-reader users; the row click is a shortcut. */}
                    <a
                      href={`/incidents/${inc.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        router.push(`/incidents/${inc.id}`);
                      }}
                      className="font-medium hover:underline"
                    >
                      {inc.title}
                    </a>
                    <span className="block text-sm text-muted-foreground sm:hidden">{inc.reference}</span>
                  </TableCell>
                  <TableCell>
                    <SeverityBadge severity={inc.severity} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={inc.status} />
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    {inc.assignee?.full_name ?? "Unassigned"}
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">
                    {formatDateTime(inc.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {data && data.total > 0 && (
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <span>
              {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft />
              </Button>
              <span className="px-2">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Next page"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight />
              </Button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
