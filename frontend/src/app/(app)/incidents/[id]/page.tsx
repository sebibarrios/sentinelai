"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { IncidentAiReport, LinkedAlerts } from "@/components/incidents/incident-intel";
import { SeverityBadge, StatusBadge } from "@/components/severity";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/table";
import { useCan } from "@/hooks/use-auth";
import {
  useAddNote,
  useAssignableUsers,
  useIncident,
  useIncidentHistory,
  useUpdateIncident,
  type IncidentInput,
} from "@/hooks/use-incidents";
import { ApiError } from "@/lib/api";
import { INCIDENT_STATUSES, SEVERITIES, type HistoryEntry, type IncidentDetail } from "@/lib/types";
import { capitalize, formatDateTime, formatRelative } from "@/lib/utils";

const UNASSIGNED = "unassigned";

export default function IncidentPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isPending, refetch } = useIncident(id);

  return (
    <>
      <Link
        href="/incidents"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Incidents
      </Link>
      {error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : isPending ? (
        <div className="flex flex-col gap-4" aria-busy>
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <IncidentView incident={data} />
      )}
    </>
  );
}

function IncidentView({ incident }: { incident: IncidentDetail }) {
  const canEdit = useCan("analyst");
  const update = useUpdateIncident(incident.id);
  const users = useAssignableUsers(canEdit);

  function change(body: IncidentInput, success: string) {
    update.mutate(body, {
      onSuccess: () => toast.success(success),
      onError: (e) => toast.error(e instanceof ApiError ? e.displayMessage : "Update failed"),
    });
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-w-0 flex-col gap-6">
        <header>
          <p className="text-sm text-muted-foreground">
            {incident.reference}, opened by {incident.created_by.full_name}{" "}
            {formatRelative(incident.created_at)}
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">{incident.title}</h1>
          <div className="mt-3 flex items-center gap-3">
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status} />
          </div>
        </header>

        <section className="rounded-lg border bg-panel p-5">
          <h2 className="mb-2 font-medium">Description</h2>
          <p className="max-w-[72ch] whitespace-pre-wrap text-muted-foreground">
            {incident.description || "No description provided."}
          </p>
        </section>

        <LinkedAlerts incidentId={incident.id} />
        <IncidentAiReport incidentId={incident.id} canEdit={canEdit} />
        <Notes incident={incident} canEdit={canEdit} />
      </div>

      <aside className="flex flex-col gap-6">
        <section className="flex flex-col gap-4 rounded-lg border bg-panel p-5">
          <h2 className="font-medium">Details</h2>
          <Field label="Status">
            <Select
              value={incident.status}
              disabled={!canEdit || update.isPending}
              onValueChange={(v) => change({ status: v as IncidentDetail["status"] }, `Status set to ${v}`)}
            >
              <SelectTrigger aria-label="Status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INCIDENT_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {capitalize(s)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Severity">
            <Select
              value={incident.severity}
              disabled={!canEdit || update.isPending}
              onValueChange={(v) =>
                change({ severity: v as IncidentDetail["severity"] }, `Severity set to ${v}`)
              }
            >
              <SelectTrigger aria-label="Severity">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEVERITIES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {capitalize(s)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Assignee">
            {canEdit ? (
              <Select
                value={incident.assignee?.id ?? UNASSIGNED}
                disabled={update.isPending}
                onValueChange={(v) =>
                  change(
                    { assignee_id: v === UNASSIGNED ? null : v },
                    v === UNASSIGNED ? "Unassigned" : "Assignee updated",
                  )
                }
              >
                <SelectTrigger aria-label="Assignee">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                  {/* Keep the current assignee selectable even before the list loads. */}
                  {incident.assignee && !users.data?.some((u) => u.id === incident.assignee!.id) && (
                    <SelectItem value={incident.assignee.id}>{incident.assignee.full_name}</SelectItem>
                  )}
                  {users.data?.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <p>{incident.assignee?.full_name ?? "Unassigned"}</p>
            )}
          </Field>
          <dl className="grid grid-cols-2 gap-y-2 border-t pt-4 text-sm">
            <dt className="text-muted-foreground">Last updated</dt>
            <dd className="text-right">{formatDateTime(incident.updated_at)}</dd>
            <dt className="text-muted-foreground">Closed</dt>
            <dd className="text-right">{formatDateTime(incident.closed_at)}</dd>
          </dl>
        </section>
        <History incidentId={incident.id} />
      </aside>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}

function Notes({ incident, canEdit }: { incident: IncidentDetail; canEdit: boolean }) {
  const [body, setBody] = useState("");
  const add = useAddNote(incident.id);

  return (
    <section className="rounded-lg border bg-panel p-5" aria-labelledby="notes-heading">
      <h2 id="notes-heading" className="mb-4 font-medium">
        Investigation notes{" "}
        <span className="font-normal text-muted-foreground">({incident.notes.length})</span>
      </h2>
      {incident.notes.length === 0 ? (
        <p className="text-muted-foreground">
          No notes yet. Record what you checked and what you found.
        </p>
      ) : (
        <ol className="flex flex-col gap-4">
          {incident.notes.map((n) => (
            <li key={n.id} className="border-l-2 border-primary/40 pl-4">
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{n.author.full_name}</span>,{" "}
                {formatDateTime(n.created_at)}
              </p>
              <p className="mt-1 max-w-[72ch] whitespace-pre-wrap">{n.body}</p>
            </li>
          ))}
        </ol>
      )}
      {canEdit && (
        <form
          className="mt-5 flex flex-col gap-2 border-t pt-5"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate(body, {
              onSuccess: () => {
                setBody("");
                toast.success("Note added");
              },
              onError: (err) =>
                toast.error(err instanceof ApiError ? err.displayMessage : "Couldn't add note"),
            });
          }}
        >
          <Label htmlFor="note">Add a note</Label>
          <Textarea
            id="note"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={10000}
            placeholder="e.g. Blocked 203.0.113.45 at the firewall; reset jdoe's password."
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={add.isPending || !body.trim()}>
              {add.isPending ? "Adding…" : "Add note"}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function describe(h: HistoryEntry): string {
  switch (h.action) {
    case "created":
      return `opened ${h.new_value}`;
    case "status_changed":
      return `changed status from ${h.old_value} to ${h.new_value}`;
    case "assigned":
      return h.new_value ? `assigned to ${h.new_value}` : "removed the assignee";
    case "note_added":
      return "added a note";
    case "alert_linked":
      return "linked an alert";
    case "updated":
      return h.field === "description" ? "edited the description" : `changed ${h.field} from ${h.old_value} to ${h.new_value}`;
  }
}

function History({ incidentId }: { incidentId: string }) {
  const { data, isPending } = useIncidentHistory(incidentId);
  return (
    <section className="rounded-lg border bg-panel p-5" aria-labelledby="history-heading">
      <h2 id="history-heading" className="mb-4 font-medium">
        History
      </h2>
      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <ol className="relative flex flex-col gap-4 border-l pl-4">
          {data?.toReversed().map((h) => (
            <li key={h.id} className="relative text-sm">
              <span aria-hidden className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-border" />
              <span className="font-medium">{h.actor.full_name}</span>{" "}
              <span className="text-muted-foreground">{describe(h)}</span>
              <div className="text-xs text-faint">{formatDateTime(h.created_at)}</div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
