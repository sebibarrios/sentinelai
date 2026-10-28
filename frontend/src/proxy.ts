import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "sentinel_session";
const PUBLIC_PATHS = ["/login", "/register"];

/** Headers only this server may set on requests to the API. Browser copies are dropped. */
const PROXY_SECRET_HEADER = "x-sentinel-proxy-secret";
const CLIENT_IP_HEADER = "x-sentinel-client-ip";

/**
 * The visitor's IP, read from a header set by trusted infrastructure in front of this
 * server (CLIENT_IP_HEADER, e.g. "x-real-ip" on Vercel). Without that setting we don't
 * guess: a header like X-Forwarded-For can be typed by anyone.
 */
function trustedClientIp(request: NextRequest): string | null {
  const header = process.env.CLIENT_IP_HEADER?.toLowerCase();
  if (!header) return null;
  const value = request.headers.get(header);
  return value ? value.split(",")[0].trim() : null;
}

/** API requests: vouch for them to the backend (see backend/app/core/proxy_auth.py). */
function forwardToApi(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete(PROXY_SECRET_HEADER);
  headers.delete(CLIENT_IP_HEADER);
  headers.delete("x-forwarded-for"); // untrusted as received; replaced below if known

  const secret = process.env.PROXY_SHARED_SECRET;
  if (secret) headers.set(PROXY_SECRET_HEADER, secret);
  const ip = trustedClientIp(request);
  if (ip) headers.set(CLIENT_IP_HEADER, ip);

  return NextResponse.next({ request: { headers } });
}

/**
 * Optimistic route guard for pages. It only checks that a session cookie exists, to
 * avoid flashing protected pages to signed-out visitors. The backend verifies the
 * token on every API call, so a forged cookie gets a page shell with no data.
 */
function guardPage(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (!hasSession && !isPublic) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if (hasSession && isPublic) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export function proxy(request: NextRequest) {
  return request.nextUrl.pathname.startsWith("/api/") ? forwardToApi(request) : guardPage(request);
}

export const config = {
  // Everything except Next internals and static files.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico)$).*)"],
};
