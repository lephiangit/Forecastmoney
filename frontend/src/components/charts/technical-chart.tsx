"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { cn } from "@/lib/utils"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, ComposedChart, Bar,
} from "recharts"

const INDICATOR_OPTIONS = [
  { key: "ma", label: "MA20 / MA50", colors: ["#f59e0b", "#8b5cf6"] },
  { key: "bb", label: "Bollinger Bands", colors: ["#06b6d4"] },
  { key: "rsi", label: "RSI", colors: ["#ec4899"] },
  { key: "macd", label: "MACD", colors: ["#10b981", "#ef4444"] },
]

interface TechnicalChartProps {
  ticker: string
  period?: string
}

export function TechnicalChart({ ticker, period = "1y" }: TechnicalChartProps) {
  const t = useT()
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set(["ma"]))

  const { data, isLoading } = useQuery({
    queryKey: ["ticker-indicators", ticker, period],
    queryFn: () => api.getTickerWithIndicators(ticker, period),
    staleTime: 60_000,
  })

  const toggleIndicator = (key: string) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (isLoading || !data?.ohlcv) {
    return <div className="flex h-80 items-center justify-center text-sm text-muted-foreground">Loading...</div>
  }

  const ohlcv = data.ohlcv
  const hasRSI = activeIndicators.has("rsi")
  const hasMACD = activeIndicators.has("macd")

  return (
    <div className="space-y-4">
      {/* Indicator Toggle Chips */}
      <div className="flex flex-wrap gap-2">
        <span className="flex items-center text-xs font-semibold uppercase text-muted-foreground">{t("indicators")}:</span>
        {INDICATOR_OPTIONS.map((ind) => (
          <button
            key={ind.key}
            onClick={() => toggleIndicator(ind.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
              activeIndicators.has(ind.key)
                ? "border-primary/60 bg-primary/10 text-primary"
                : "border-border bg-secondary text-muted-foreground hover:text-foreground",
            )}
          >
            {ind.label}
          </button>
        ))}
      </div>

      {/* Main Price Chart with MA + BB overlays */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={ohlcv}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
              tickFormatter={(v: string) => v.slice(5)}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => v > 1000 ? `${(v/1000).toFixed(0)}k` : v.toFixed(2)}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
              formatter={(val: any, name: any) => [typeof val === "number" ? val.toFixed(4) : val, name]}
            />

            {/* Price line */}
            <Line type="monotone" dataKey="close" stroke="hsl(var(--foreground))" strokeWidth={1.5} dot={false} name="Price" />

            {/* MA overlays */}
            {activeIndicators.has("ma") && (
              <>
                <Line type="monotone" dataKey="ma20" stroke="#f59e0b" strokeWidth={1} dot={false} name="MA20" strokeDasharray="2 2" />
                <Line type="monotone" dataKey="ma50" stroke="#8b5cf6" strokeWidth={1} dot={false} name="MA50" strokeDasharray="4 2" />
              </>
            )}

            {/* Bollinger Bands */}
            {activeIndicators.has("bb") && (
              <>
                <Line type="monotone" dataKey="bb_upper" stroke="#06b6d4" strokeWidth={1} dot={false} name="BB Upper" opacity={0.6} />
                <Line type="monotone" dataKey="bb_lower" stroke="#06b6d4" strokeWidth={1} dot={false} name="BB Lower" opacity={0.6} />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* RSI Sub-Chart */}
      {hasRSI && (
        <div className="h-28">
          <p className="mb-1 text-xs font-semibold text-muted-foreground">RSI (14)</p>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={ohlcv}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={false} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} ticks={[30, 50, 70]} />
              <Tooltip
                contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
                formatter={(val: any) => [Number(val).toFixed(1), "RSI"]}
              />
              <Line type="monotone" dataKey="rsi" stroke="#ec4899" strokeWidth={1.5} dot={false} />
              {/* Overbought / Oversold reference lines */}
              <Line type="monotone" dataKey={() => 70} stroke="#ef4444" strokeWidth={0.5} strokeDasharray="3 3" dot={false} />
              <Line type="monotone" dataKey={() => 30} stroke="#10b981" strokeWidth={0.5} strokeDasharray="3 3" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* MACD Sub-Chart */}
      {hasMACD && (
        <div className="h-28">
          <p className="mb-1 text-xs font-semibold text-muted-foreground">MACD</p>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={ohlcv}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={false} axisLine={false} />
              <YAxis tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} />
              <Tooltip
                contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
                formatter={(val: any, name: any) => [Number(val).toFixed(4), name]}
              />
              <Line type="monotone" dataKey="macd" stroke="#10b981" strokeWidth={1.5} dot={false} name="MACD" />
              <Line type="monotone" dataKey="macd_signal" stroke="#ef4444" strokeWidth={1} dot={false} name="Signal" strokeDasharray="3 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
