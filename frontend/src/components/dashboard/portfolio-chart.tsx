"use client"

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { ForecastPoint } from "@/lib/types"
import { formatCurrency } from "@/lib/format"

export function PortfolioChart({ data }: { data: ForecastPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="pv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fcd535" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#fcd535" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="time"
          tick={{ fill: "#707a8a", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "#2b3139" }}
          minTickGap={40}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis
          tick={{ fill: "#707a8a", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={56}
          domain={["dataMin", "dataMax"]}
          tickFormatter={(v: number) => formatCurrency(v, { compact: true })}
        />
        <Tooltip
          contentStyle={{
            background: "#12161c",
            border: "1px solid #2b3139",
            borderRadius: 8,
            color: "#eaecef",
            fontSize: 12,
          }}
          labelStyle={{ color: "#707a8a" }}
          formatter={(v: any) => [formatCurrency(Number(v) || 0), "Value"]}
        />
        <Area type="monotone" dataKey="value" stroke="#fcd535" strokeWidth={2} fill="url(#pv)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
