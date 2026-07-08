"use client"

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { ForecastPoint } from "@/lib/types"
import { formatCurrency } from "@/lib/format"
import { Activity } from "lucide-react"

export function PortfolioChart({ data }: { data: ForecastPoint[] }) {
  if (!data || data.length <= 1) {
    return (
      <div className="flex h-[260px] w-full flex-col items-center justify-center rounded-lg border border-border border-dashed bg-secondary/30">
        <Activity className="mb-2 h-6 w-6 text-muted-foreground opacity-50" />
        <p className="text-sm font-medium text-muted-foreground">No history available</p>
        <p className="mt-1 text-xs text-muted-foreground opacity-70">Start trading to see your portfolio chart</p>
      </div>
    )
  }

  // Determine color based on overall trend
  const startValue = data[0].value
  const endValue = data[data.length - 1].value
  const isPositive = endValue >= startValue
  
  const color = isPositive ? "#0ebd8b" : "#f6465d" // Green or Red

  return (
    <ResponsiveContainer width="100%" height={260} minWidth={0} minHeight={0}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="pvColor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
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
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill="url(#pvColor)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
