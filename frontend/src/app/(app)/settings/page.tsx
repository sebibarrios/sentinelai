"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/table";
import { useMe } from "@/hooks/use-auth";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { capitalize, formatDateTime } from "@/lib/utils";

function errorText(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.displayMessage : fallback;
}

export default function SettingsPage() {
  const { data: me } = useMe();

  return (
    <>
      <PageHeader title="Settings" description="Manage your profile and password." />
      {!me ? (
        <Skeleton className="h-64 w-full max-w-2xl" />
      ) : (
        <div className="flex max-w-2xl flex-col gap-6">
          <ProfileForm me={me} />
          <PasswordForm />
        </div>
      )}
    </>
  );
}

function ProfileForm({ me }: { me: User }) {
  const qc = useQueryClient();
  const [name, setName] = useState(me.full_name);
  const save = useMutation({
    mutationFn: () => api.patch<User>("/users/me", { full_name: name }),
    onSuccess: (user) => {
      qc.setQueryData(["me"], user);
      toast.success("Profile saved");
    },
    onError: (e) => toast.error(errorText(e, "Couldn't save profile")),
  });

  return (
    <form
      className="flex flex-col gap-4 rounded-lg border bg-panel p-6"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <h2 className="font-medium">Profile</h2>
      <div className="flex flex-col gap-2">
        <Label htmlFor="name">Full name</Label>
        <Input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      </div>
      <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
        <dt className="text-muted-foreground">Email</dt>
        <dd>{me.email}</dd>
        <dt className="text-muted-foreground">Role</dt>
        <dd>{capitalize(me.role)}</dd>
        <dt className="text-muted-foreground">Last sign-in</dt>
        <dd>{formatDateTime(me.last_login_at)}</dd>
      </dl>
      <div>
        <Button type="submit" disabled={save.isPending || !name.trim() || name === me.full_name}>
          {save.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && next !== confirm;

  const change = useMutation({
    mutationFn: () =>
      api.post<void>("/users/me/password", { current_password: current, new_password: next }),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password changed");
    },
    onError: (e) => toast.error(errorText(e, "Couldn't change password")),
  });

  return (
    <form
      className="flex flex-col gap-4 rounded-lg border bg-panel p-6"
      onSubmit={(e) => {
        e.preventDefault();
        change.mutate();
      }}
    >
      <h2 className="font-medium">Password</h2>
      <div className="flex flex-col gap-2">
        <Label htmlFor="current">Current password</Label>
        <Input
          id="current"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="new">New password</Label>
          <Input
            id="new"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="confirm">Confirm new password</Label>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            aria-invalid={mismatch}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
      </div>
      <p className={mismatch ? "text-sm text-sev-critical" : "text-sm text-muted-foreground"}>
        {mismatch ? "Passwords don't match." : "At least 10 characters, with letters and numbers."}
      </p>
      <div>
        <Button type="submit" disabled={change.isPending || !current || !next || next !== confirm}>
          {change.isPending ? "Changing…" : "Change password"}
        </Button>
      </div>
    </form>
  );
}
