"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { capitalize } from "@/lib/utils";
import { INCIDENT_STATUSES, type IncidentStatus } from "@/lib/types";

const STATUS_FILL: Record<IncidentStatus, string> = {
  open: "var(--fg)",
  investigating: "var(--accent)",
  contained: "var(--sev-medium)",
  resolved: "var(--sev-low)",
  closed: "var(--fg-faint)",
};

export function StatusChart({ counts }: { counts: Record<IncidentStatus, number> }) {
  const data = INCIDENT_STATUSES.map((s) => ({ status: capitalize(s), key: s, count: counts[s] }));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <XAxis type="number" allowDecimals={false} domain={[0, "dataMax"]} hide />
          <YAxis
            type="category"
            dataKey="status"
            width={96}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--fg-muted)", fontSize: 13 }}
          />
          <Tooltip
            cursor={{ fill: "var(--raised)" }}
            contentStyle={{
              background: "var(--raised)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              color: "var(--fg)",
            }}
            labelStyle={{ color: "var(--fg)" }}
            itemStyle={{ color: "var(--fg-muted)" }}
          />
          <Bar dataKey="count" name="Incidents" radius={[0, 4, 4, 0]} barSize={14}>
            {data.map((d) => (
              <Cell key={d.key} fill={STATUS_FILL[d.key]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
