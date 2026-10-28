import type { NextConfig } from "next";

const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

const isDev = process.env.NODE_ENV !== "production";

/*
  Content-Security-Policy.

  Next.js's nonce-based CSP requires rendering every page per request, which is
  incompatible with the prerendered static shells this app uses (Cache Components /
  Partial Prerendering). So scripts allow 'unsafe-inline' for Next's own bootstrap
  code, and XSS defense rests on React's output escaping plus never rendering raw
  HTML. The policy still blocks the things that matter most:
  - scripts, styles, fonts and images from any other origin
  - connect-src 'self': injected code can't send data to an outside server
  - framing (clickjacking), <object>/<embed>, <base> hijacking, off-site form posts
  Dev mode adds 'unsafe-eval', which React uses only for development error overlays.
*/
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'", // charts and Radix set inline style attributes
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${isDev ? " ws:" : ""}`, // ws: is the dev hot-reload socket
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // Browsers ignore HSTS over plain HTTP, so this is harmless locally and
  // takes effect once deployed behind HTTPS.
  ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]),
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Small self-contained server for the Docker image (set in frontend/Dockerfile).
  // Off otherwise: `next start` and Vercel don't use it.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only talks to this origin; Next.js forwards /api/* to FastAPI.
  // That keeps the session cookie first-party and the backend URL out of client code.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
