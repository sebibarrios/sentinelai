"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
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
import { useUpdateIncident } from "@/hooks/use-incidents";
import { ApiError } from "@/lib/api";
import type { IncidentDetail } from "@/lib/types";

export function EditIncidentDialog({ incident }: { incident: IncidentDetail }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(incident.title);
  const [description, setDescription] = useState(incident.description);
  const update = useUpdateIncident(incident.id);
  const unchanged = title.trim() === incident.title && description === incident.description;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) {
          // Start from the latest saved values each time the dialog opens.
          setTitle(incident.title);
          setDescription(incident.description);
          update.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil /> Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate(
              { title: title.trim(), description },
              {
                onSuccess: () => {
                  toast.success("Incident updated");
                  setOpen(false);
                },
              },
            );
          }}
        >
          <DialogHeader>
            <DialogTitle>Edit {incident.reference}</DialogTitle>
            <DialogDescription>Changes are recorded in the incident history.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-title">Title</Label>
            <Input
              id="edit-title"
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-description">Description</Label>
            <Textarea
              id="edit-description"
              className="min-h-48"
              value={description}
              maxLength={10000}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          {update.error && (
            <p role="alert" className="text-sm text-sev-critical">
              {update.error instanceof ApiError ? update.error.displayMessage : "Couldn't save changes."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending || unchanged || title.trim().length < 3}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
