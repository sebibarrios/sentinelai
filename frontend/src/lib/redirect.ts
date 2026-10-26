/**
 * Validate a post-login redirect target (the ?next= parameter).
 *
 * String checks like "starts with / but not //" aren't enough: browsers treat "\" as
 * "/", so "/\evil.com" becomes "//evil.com", a different site. Instead, resolve the
 * value exactly as the browser would and accept it only if it stays on our origin.
 */
export function safeRedirectPath(next: string | null, origin: string, fallback = "/dashboard"): string {
  if (!next) return fallback;
  try {
    const url = new URL(next, origin);
    if (url.origin !== new URL(origin).origin) return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}
