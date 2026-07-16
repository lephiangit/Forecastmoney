"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Search, TrendingUp, TrendingDown, Star } from "lucide-react"
import { api } from "@/lib/api"
import { useT, useAuthStore } from "@/lib/store"
import type { TranslationKey } from "@/lib/i18n"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { Sparkline } from "@/components/ui/sparkline"
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

const FILTERS: { value: string; key: TranslationKey }[] = [
  { value: "all", key: "allAssets" },
  { value: "watchlist", key: "watchlist" },
  { value: "crypto", key: "crypto" },
  { value: "index", key: "indices" },
  { value: "commodity", key: "commodities" },
  { value: "stock", key: "stocks" },
]

export default function MarketsPage() {
  const t = useT()
  const [filter, setFilter] = useState("all")
  const [search, setSearch] = useState("")
  const { data, isError, refetch } = useQuery({ queryKey: ["markets"], queryFn: api.getMarkets, refetchInterval: 30000 })

  const { user } = useAuthStore()
  const { data: watchlist = [], refetch: refetchWatchlist } = useQuery({ queryKey: ["watchlist"], queryFn: api.getWatchlist, enabled: !!user })

  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    const delayDebounce = setTimeout(async () => {
      if (search.trim().length >= 2) {
        setIsSearching(true)
        try {
          const results = await api.searchTickers(search)
          setSearchResults(results)
        } catch {
          setSearchResults([])
        } finally {
          setIsSearching(false)
        }
      } else {
        setSearchResults([])
      }
    }, 500)

    return () => clearTimeout(delayDebounce)
  }, [search])

  const filtered = (data ?? [])
    .filter((a) => filter === "all" || a.category === filter || (filter === "watchlist" && watchlist.includes(a.ticker)))
    .filter((a) => a.ticker.toLowerCase().includes(search.toLowerCase()) || a.name.toLowerCase().includes(search.toLowerCase()))

  const toggleWatchlist = async (e: React.MouseEvent, ticker: string) => {
    e.preventDefault()
    if (watchlist.includes(ticker)) {
      await api.removeWatchlist(ticker)
    } else {
      await api.addWatchlist(ticker)
    }
    refetchWatchlist()
    setTimeout(() => refetch(), 100) // Trigger refetch to update prices list immediately
  }

  return (
    <div>
      <PageHeader title={t("marketExplorer")} subtitle={t("whatIsHappening")} />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                filter === f.value
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-secondary text-muted-foreground hover:text-foreground",
              )}
            >
              {t(f.key)}
            </button>
          ))}
        </div>
        <div className="relative sm:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchAssets")}
            className="w-full rounded-md border border-border bg-secondary py-2 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/50"
          />
        </div>
      </div>

      {isError ? (
        <ErrorCard onRetry={() => refetch()} />
      ) : !data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3 font-medium w-8"></th>
                <th className="px-4 py-3 font-medium">{t("asset")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("price")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("change24h")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("high24h")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("low24h")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("volume")}</th>
                <th className="px-4 py-3 text-right font-medium">{t("chart")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a, i) => {
                const pos = a.changePercent >= 0
                return (
                  <motion.tr
                    key={a.ticker}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40"
                  >
                    <td className="px-4 py-3">
                      <button onClick={(e) => toggleWatchlist(e, a.ticker)} className="text-muted-foreground hover:text-primary transition-colors">
                        <Star className={cn("h-4 w-4", watchlist.includes(a.ticker) && "fill-primary text-primary")} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/forecast/${a.ticker}`} className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                          {a.ticker.slice(0, 3)}
                        </div>
                        <div>
                          <p className="font-mono font-semibold text-card-foreground">{a.ticker}</p>
                          <p className="text-xs text-muted-foreground">{a.name}</p>
                        </div>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(a.price, { currency: a.ticker })}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={cn("inline-flex items-center justify-end gap-1 font-mono font-medium", pos ? "text-positive" : "text-negative")}>
                        {pos ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                        {formatPercent(a.changePercent)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(a.high24h, { currency: a.ticker })}</td>
                    <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(a.low24h, { currency: a.ticker })}</td>
                    <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatNumber(a.volume, { compact: true })}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end">
                        <Sparkline data={a.sparkline} positive={pos} width={96} height={28} />
                      </div>
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="py-10 text-center text-sm text-muted-foreground">No assets found.</p>
          )}
        </div>
      )}

      {/* yfinance Search Results Section */}
      {search.trim().length >= 2 && (
        <div className="mt-6 rounded-lg border border-border bg-card p-5">
          <h3 className="mb-4 font-semibold text-card-foreground flex items-center gap-2">
            <Search className="h-4.5 w-4.5 text-primary" />
            <span>Kết quả tìm kiếm yfinance cho "{search}"</span>
          </h3>
          
          {isSearching ? (
            <div className="py-8 text-center text-sm text-muted-foreground">Đang tìm kiếm trên yfinance...</div>
          ) : searchResults.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">Không tìm thấy mã nào tương tự trên yfinance.</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {searchResults.map((res) => {
                const isStarred = watchlist.includes(res.symbol)
                return (
                  <div key={res.symbol} className="flex items-center justify-between rounded-md border border-border/50 bg-background p-3 hover:border-primary/40 transition-colors">
                    <div className="flex-1 min-w-0 pr-3">
                      <Link href={`/forecast/${res.symbol}`} className="block group">
                        <span className="font-mono font-bold text-sm text-primary block truncate group-hover:underline">{res.symbol}</span>
                        <span className="text-xs text-card-foreground block truncate font-medium">{res.name}</span>
                        <span className="text-[10px] text-muted-foreground block truncate font-mono uppercase mt-0.5">{res.exchange} · {res.type}</span>
                      </Link>
                    </div>
                    <button
                      onClick={async (e) => {
                        e.preventDefault()
                        if (isStarred) {
                          await api.removeWatchlist(res.symbol)
                        } else {
                          await api.addWatchlist(res.symbol)
                        }
                        refetchWatchlist()
                        setTimeout(() => refetch(), 100) // Refresh markets page overview prices
                      }}
                      className="rounded p-2 text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors"
                    >
                      <Star className={cn("h-4 w-4", isStarred && "fill-primary text-primary")} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
