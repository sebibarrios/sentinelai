"use client";

import { useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useRegister } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const register = useRegister();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const error =
    register.error instanceof ApiError
      ? register.error.displayMessage
      : register.error
        ? "Couldn't reach the server."
        : null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        register.mutate(form);
      }}
      className="flex flex-col gap-5"
      noValidate
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Create an account</h1>
        <p className="mt-1 text-muted-foreground">
          New accounts start with read-only access. An admin can grant analyst permissions.
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="full_name">Full name</Label>
        <Input id="full_name" autoComplete="name" value={form.full_name} onChange={set("full_name")} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" value={form.email} onChange={set("email")} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={set("password")}
          aria-describedby="password-hint"
        />
        <p id="password-hint" className="text-xs text-muted-foreground">
          At least 10 characters, with letters and numbers.
        </p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-sev-critical">
          {error}
        </p>
      )}
      <Button
        type="submit"
        disabled={register.isPending || !form.full_name || !form.email || !form.password}
      >
        {register.isPending ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
