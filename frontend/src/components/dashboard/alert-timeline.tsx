"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { SEVERITY_COLOR } from "@/components/severity";
import { capitalize } from "@/lib/utils";
import type { TimelinePoint } from "@/lib/types";

const ORDER = ["low", "medium", "high", "critical"] as const;

export function AlertTimeline({ points, hourly }: { points: TimelinePoint[]; hourly: boolean }) {
  const fmt = new Intl.DateTimeFormat("en-US", hourly ? { hour: "numeric" } : { month: "short", day: "numeric" });
  const data = points.map((p) => ({ ...p, label: fmt.format(new Date(p.bucket)) }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
            tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={40}
            tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
          />
          <Tooltip
            cursor={{ fill: "var(--raised)" }}
            contentStyle={{
              background: "var(--raised)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              color: "var(--fg)",
            }}
            formatter={(value, name) => [value, capitalize(String(name))]}
          />
          {ORDER.map((sev, i) => (
            <Bar
              key={sev}
              dataKey={sev}
              stackId="alerts"
              fill={SEVERITY_COLOR[sev]}
              radius={i === ORDER.length - 1 ? [3, 3, 0, 0] : 0}
              maxBarSize={28}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
