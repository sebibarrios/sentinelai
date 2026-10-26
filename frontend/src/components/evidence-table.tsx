import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { SecurityEvent } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

const OUTCOME_STYLE: Record<SecurityEvent["outcome"], string> = {
  success: "text-sev-low",
  allowed: "text-sev-low",
  failure: "text-sev-high",
  denied: "text-sev-high",
};

export function EventsTable({ events, dense = false }: { events: SecurityEvent[]; dense?: boolean }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-40">Time (local)</TableHead>
          <TableHead className="w-24">Outcome</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Source</TableHead>
          <TableHead className="hidden md:table-cell">Destination</TableHead>
          <TableHead className={cn("hidden w-16 lg:table-cell", dense && "lg:hidden")}>Geo</TableHead>
          <TableHead className={cn("hidden xl:table-cell", dense && "xl:hidden")}>User agent</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.id}>
            <TableCell className="whitespace-nowrap text-muted-foreground">
              {formatDateTime(e.occurred_at)}
            </TableCell>
            <TableCell className={cn("font-medium", OUTCOME_STYLE[e.outcome])}>{e.outcome}</TableCell>
            <TableCell>{e.username ?? <span className="text-faint">—</span>}</TableCell>
            <TableCell className="font-mono text-sm">{e.src_ip}</TableCell>
            <TableCell className="hidden font-mono text-sm md:table-cell">
              {e.dst_ip ? `${e.dst_ip}${e.dst_port != null ? `:${e.dst_port}` : ""}` : "—"}
            </TableCell>
            <TableCell className={cn("hidden text-muted-foreground lg:table-cell", dense && "lg:hidden")}>
              {e.country ?? "—"}
            </TableCell>
            <TableCell
              className={cn(
                "hidden max-w-[16rem] truncate font-mono text-xs text-muted-foreground xl:table-cell",
                dense && "xl:hidden",
              )}
              title={e.user_agent ?? undefined}
            >
              {e.user_agent ?? "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
