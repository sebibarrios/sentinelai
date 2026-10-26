"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAssignableUsers, useCreateIncident } from "@/hooks/use-incidents";
import { ApiError } from "@/lib/api";
import { SEVERITIES, type Severity } from "@/lib/types";
import { capitalize } from "@/lib/utils";

const UNASSIGNED = "unassigned";

export function NewIncidentDialog({ trigger }: { trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [assignee, setAssignee] = useState(UNASSIGNED);
  const create = useCreateIncident();
  const users = useAssignableUsers(open);
  const router = useRouter();

  function reset() {
    setTitle("");
    setDescription("");
    setSeverity("medium");
    setAssignee(UNASSIGNED);
    create.reset();
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        title,
        description,
        severity,
        assignee_id: assignee === UNASSIGNED ? null : assignee,
      },
      {
        onSuccess: (inc) => {
          toast.success(`Created ${inc.reference}`);
          setOpen(false);
          reset();
          router.push(`/incidents/${inc.id}`);
        },
      },
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New incident</DialogTitle>
            <DialogDescription>Open an investigation and optionally assign an owner.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="inc-title">Title</Label>
            <Input
              id="inc-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Repeated failed logins on VPN"
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="inc-desc">Description</Label>
            <Textarea
              id="inc-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What was observed, and where?"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="inc-sev">Severity</Label>
              <Select value={severity} onValueChange={(v) => setSeverity(v as Severity)}>
                <SelectTrigger id="inc-sev">
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
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="inc-assignee">Assignee</Label>
              <Select value={assignee} onValueChange={setAssignee}>
                <SelectTrigger id="inc-assignee">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                  {users.data?.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {create.error && (
            <p role="alert" className="text-sm text-sev-critical">
              {create.error instanceof ApiError ? create.error.displayMessage : "Couldn't create the incident."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || title.trim().length < 3}>
              {create.isPending ? "Creating…" : "Create incident"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
