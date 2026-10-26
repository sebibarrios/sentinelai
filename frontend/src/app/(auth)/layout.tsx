import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(420px,520px)]">
      <section className="relative hidden overflow-hidden border-r bg-panel lg:flex lg:flex-col lg:justify-between lg:p-12">
        <Logo />
        <div className="max-w-md">
          <p className="text-2xl font-semibold leading-[1.1] tracking-tight">
            Every alert traced back to the log line that caused it.
          </p>
          <p className="mt-4 text-md text-muted-foreground">
            Detection rules flag what happened. AI explains it and suggests what to check next, and
            the two are never mixed.
          </p>
        </div>
        <ThreatBarMotif />
      </section>
      <section className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          {children}
        </div>
      </section>
    </div>
  );
}

/** Echo of the dashboard's severity bar, as a quiet brand element. */
function ThreatBarMotif() {
  const segments = [
    { w: 8, c: "var(--sev-critical)" },
    { w: 22, c: "var(--sev-high)" },
    { w: 30, c: "var(--sev-medium)" },
    { w: 40, c: "var(--sev-low)" },
  ];
  return (
    <div aria-hidden className="flex h-2 w-full max-w-md gap-1 opacity-80">
      {segments.map((s, i) => (
        <span key={i} className="rounded-full" style={{ flexGrow: s.w, background: s.c }} />
      ))}
    </div>
  );
}
