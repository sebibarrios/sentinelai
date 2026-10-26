/**
 * Thin fetch wrapper for the SentinelAI API.
 *
 * Requests go to relative /api/v1/... URLs. Next.js rewrites them to the FastAPI
 * service (see next.config.ts), so the session cookie is first-party and the
 * backend URL never appears in client code.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { field?: string; message: string }[] | null,
  ) {
    super(message);
  }

  /** First field-level message if present, otherwise the top-level message. */
  get displayMessage(): string {
    return this.details?.[0]?.message ?? this.message;
  }
}

type Query = Record<string, string | number | undefined | null>;

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return `/api/v1${path}${qs ? `?${qs}` : ""}`;
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const res = await fetch(buildUrl(path, query), {
    method,
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      // Custom header: browsers won't let other sites add it cross-origin (CSRF defense-in-depth).
      "X-Requested-With": "SentinelAI",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // Non-JSON response (e.g. proxy error page)
  }

  if (!res.ok) {
    const err = (data as { error?: { code: string; message: string; details?: [] } })?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "network_error",
      err?.message ?? (res.status >= 500 ? "The server is unavailable. Try again shortly." : res.statusText),
      err?.details,
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};
