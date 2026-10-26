import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError
      ? error.status === 403
        ? "Your role doesn't have access to this. Ask an admin if you need it."
        : error.displayMessage
      : "Couldn't reach the server. Check that the API is running.";
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-sev-critical/40 bg-sev-critical/5 p-5">
      <div className="flex items-center gap-2 font-medium text-sev-critical">
        <AlertTriangle className="size-4" /> Something went wrong
      </div>
      <p className="text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="text-md font-medium">{title}</p>
      <p className="max-w-sm text-muted-foreground">{description}</p>
      {action && <div className="pt-3">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
