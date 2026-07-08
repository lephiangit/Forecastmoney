"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { TrendingUp, TrendingDown } from "lucide-react"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { formatCurrency } from "@/lib/format"

const TICKER_ORDER = ["BTC", "ETH", "SP500", "NASDAQ", "DOW", "GOLD", "OIL"]

export function MarketTicker() {
  const { data } = useQuery({
    queryKey: ["markets-ticker"],
    queryFn: api.getMarkets,
    refetchInterval: 30_000,
  })

  const assets = (data ?? []).filter((a) => a.ticker && typeof a.price === "number")

  if (!assets.length) {
    return <div className="sticky top-14 z-40 h-9 border-b border-t-2 border-t-primary border-border bg-bg-secondary" />
  }

  let baseList = [...assets]
  while (baseList.length > 0 && baseList.length < 20) {
    baseList = [...baseList, ...assets]
  }

  const loop = [...baseList, ...baseList]

  return (
    <div className="sticky top-14 z-40 overflow-hidden border-b border-t-2 border-t-primary border-border bg-bg-secondary">
      <div className="ticker-track flex w-max items-center whitespace-nowrap py-2">
        {loop.map((a, i) => {
          const pos = a.changePercent >= 0
          return (
            <Link
              key={`${a.ticker}-${i}`}
              href={`/forecast/${a.ticker}`}
              className="flex items-center gap-2 border-r border-border px-5 text-sm transition-colors hover:bg-accent/40"
            >
              <span className="font-semibold text-foreground">{a.ticker}</span>
              <span className="font-mono text-muted-foreground">
                {formatCurrency(a.price, { currency: a.ticker, decimals: a.price > 1000 ? 0 : 2 })}
              </span>
              <span className={cn("flex items-center gap-0.5 font-mono text-xs font-medium", pos ? "text-positive" : "text-negative")}>
                {pos ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {pos ? "+" : ""}
                {(Number(a.changePercent) || 0).toFixed(2)}%
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
