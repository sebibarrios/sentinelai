import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "sentinel_session";
const PUBLIC_PATHS = ["/login", "/register"];

/**
 * Optimistic route guard. It only checks that a session cookie exists, to avoid
 * flashing protected pages to signed-out visitors. The backend verifies the token
 * on every API call, so a forged cookie gets a page shell with no data.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p);

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

export const config = {
  // Skip API calls (proxied to FastAPI), Next internals, and static files.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|ico)$).*)"],
};
