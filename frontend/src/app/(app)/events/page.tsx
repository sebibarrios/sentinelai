"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";

import { EventsTable } from "@/components/evidence-table";
import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/table";
import { useDebounced } from "@/hooks/use-debounced";
import { useEvents, type EventFilters } from "@/hooks/use-security";

const ALL = "all";
const PAGE_SIZE = 50;
const IP_PATTERN = /^[0-9a-fA-F.:]+$/;

/** Filters can come from the URL (dashboard links); keyed so each link starts fresh. */
export default function EventsPage() {
  const params = useSearchParams();
  return (
    <EventsView
      key={params.toString()}
      initial={{
        category: ["auth", "network"].includes(params.get("category") ?? "") ? params.get("category")! : ALL,
        outcome: ["success", "failure", "allowed", "denied"].includes(params.get("outcome") ?? "")
          ? params.get("outcome")!
          : ALL,
        username: params.get("username") ?? "",
        ip: params.get("src_ip") ?? "",
      }}
    />
  );
}

function EventsView({
  initial,
}: {
  initial: { category: string; outcome: string; username: string; ip: string };
}) {
  const [category, setCategory] = useState<string>(initial.category);
  const [outcome, setOutcome] = useState<string>(initial.outcome);
  const [username, setUsername] = useState(initial.username);
  const [ip, setIp] = useState(initial.ip);
  const [page, setPage] = useState(1);
  const user = useDebounced(username.trim());
  const ipQuery = useDebounced(ip.trim());
  const ipValid = ipQuery === "" || IP_PATTERN.test(ipQuery);

  const { data, error, isPending, isPlaceholderData, refetch } = useEvents({
    category: category === ALL ? undefined : (category as EventFilters["category"]),
    outcome: outcome === ALL ? undefined : (outcome as EventFilters["outcome"]),
    username: user || undefined,
    src_ip: ipValid && ipQuery ? ipQuery : undefined,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <>
      <PageHeader
        title="Events"
        description="Every normalized log event, newest first. Filter to follow an account or an address."
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          placeholder="Exact username"
          aria-label="Filter by username"
          value={username}
          maxLength={128}
          onChange={(e) => {
            setUsername(e.target.value);
            setPage(1);
          }}
        />
        <Input
          placeholder="Exact source IP"
          aria-label="Filter by source IP"
          value={ip}
          aria-invalid={!ipValid}
          className="font-mono"
          onChange={(e) => {
            setIp(e.target.value);
            setPage(1);
          }}
        />
        <Select
          value={category}
          onValueChange={(v) => {
            setCategory(v);
            setPage(1);
          }}
        >
          <SelectTrigger aria-label="Filter by category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            <SelectItem value="auth">Authentication</SelectItem>
            <SelectItem value="network">Network</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={outcome}
          onValueChange={(v) => {
            setOutcome(v);
            setPage(1);
          }}
        >
          <SelectTrigger aria-label="Filter by outcome">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All outcomes</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="failure">Failure</SelectItem>
            <SelectItem value="allowed">Allowed</SelectItem>
            <SelectItem value="denied">Denied</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border bg-panel">
        {error ? (
          <div className="p-4">
            <ErrorState error={error} onRetry={() => refetch()} />
          </div>
        ) : isPending ? (
          <div className="flex flex-col gap-2 p-4" aria-busy>
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            title="No events match"
            description="Usernames and IPs must match exactly. Upload a log if you haven't yet."
          />
        ) : (
          <div className={isPlaceholderData ? "opacity-60" : undefined}>
            <EventsTable events={data.items} />
          </div>
        )}
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
      </div>
    </>
  );
}
