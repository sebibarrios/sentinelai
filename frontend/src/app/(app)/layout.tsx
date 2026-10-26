import { Suspense } from "react";

import { AppShell } from "@/components/layout/app-shell";

/*
  With Cache Components, Next.js prerenders a static shell for every route.
  The app shell reads the URL (active nav item, route params), which is only known
  at request time, so it streams in behind this Suspense boundary.
*/
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<ShellFallback />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

function ShellFallback() {
  return (
    <div className="flex min-h-dvh" aria-busy>
      <aside className="hidden w-60 shrink-0 border-r bg-panel lg:block" />
      <div className="flex-1">
        <div className="h-14 border-b" />
      </div>
    </div>
  );
}
