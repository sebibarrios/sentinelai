"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useLogin } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { safeRedirectPath } from "@/lib/redirect";

/** Where to go after sign-in: the ?next= page, but only if it stays on this site. */
function safeNextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return safeRedirectPath(next, window.location.origin);
}

export default function LoginPage() {
  const login = useLogin();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // The redirect target is read at submit time (not with useSearchParams) so the
  // form can be prerendered as static HTML and appears instantly.
  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => router.replace(safeNextPath()) });
  }

  const error = login.error instanceof ApiError ? login.error.displayMessage : login.error ? "Couldn't reach the server." : null;

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1 text-muted-foreground">Use your SentinelAI account.</p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={!!error}
          aria-describedby={error ? "login-error" : undefined}
        />
      </div>
      {error && (
        <p id="login-error" role="alert" className="text-sm text-sev-critical">
          {error}
        </p>
      )}
      <Button type="submit" disabled={login.isPending || !email || !password}>
        {login.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <p className="text-sm text-muted-foreground">
        No account yet?{" "}
        <Link href="/register" className="text-primary hover:underline">
          Create one
        </Link>
      </p>
    </form>
  );
}

