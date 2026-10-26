# SentinelAI frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui (Radix) + TanStack Query.

```bash
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

- All API calls go to relative `/api/v1/...` URLs; `next.config.ts` rewrites them to `BACKEND_URL`, so the session cookie stays first-party.
- `src/proxy.ts` redirects signed-out visitors to `/login`. It's a convenience check only; the backend authorizes every request.
- Design tokens live in `src/app/globals.css`. Severity colors are the only saturated hues in the UI.

See the root README and `docs/ARCHITECTURE.md` for the full picture.
