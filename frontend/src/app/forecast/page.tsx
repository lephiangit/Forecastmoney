"use client"

import { useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Search, Sparkles, TrendingUp, TrendingDown, Minus, ArrowUpRight, Star } from "lucide-react"
import { api } from "@/lib/api"
import { useT, useAuthStore } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton, ErrorCard, EmptyState } from "@/components/ui/states"
import { ConfidencePill } from "@/components/ui/tags"
import { formatCurrency, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function ForecastIndexPage() {
  const t = useT()
  const [search, setSearch] = useState("")
  const [adding, setAdding] = useState(false)
  const { data, isError, refetch } = useQuery({ queryKey: ["forecasts"], queryFn: api.getForecasts })
  const { user } = useAuthStore()
  const { data: watchlist = [], refetch: refetchWatchlist } = useQuery({ queryKey: ["watchlist"], queryFn: api.getWatchlist, enabled: !!user })

  const handleAddNew = async () => {
    if (!search || !user) return
    setAdding(true)
    await api.addWatchlist(search.toUpperCase())
    setSearch("")
    refetchWatchlist()
    refetch()
    setAdding(false)
  }

  const filtered = (data ?? []).filter(
    (f) => f.ticker.toLowerCase().includes(search.toLowerCase()) || f.name.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div>
      <PageHeader title={t("forecastExplorer")} subtitle={t("whatAiThinks")} />

      <div className="mb-5 flex justify-end">
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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState 
          title={search ? `Không tìm thấy "${search}" trong danh sách hiện tại.` : "No forecasts found."} 
          icon={Sparkles} 
          action={
            search && user ? (
              <button
                onClick={handleAddNew}
                disabled={adding}
                className="mt-2 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {adding ? "Đang thêm..." : `Thêm ${search.toUpperCase()} vào yêu thích`}
              </button>
            ) : null
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((f, i) => {
            const Icon = f.direction === "up" ? TrendingUp : f.direction === "down" ? TrendingDown : Minus
            const tone =
              f.direction === "up" ? "text-positive" : f.direction === "down" ? "text-negative" : "text-muted-foreground"
            return (
              <motion.div
                key={f.ticker}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: i * 0.04 }}
                whileHover={{ y: -3 }}
              >
                <Link
                  href={`/forecast/${f.ticker}`}
                  className="group flex flex-col rounded-lg border border-border bg-card p-5 transition-colors hover:border-primary/40"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                        {f.ticker.slice(0, 3)}
                      </span>
                      <div>
                        <p className="font-mono text-sm font-bold text-card-foreground">{f.ticker}</p>
                        <p className="text-xs text-muted-foreground">{f.name}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {user && (
                        <button 
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            if (watchlist.includes(f.ticker)) {
                              api.removeWatchlist(f.ticker).then(() => { refetchWatchlist(); refetch() })
                            } else {
                              api.addWatchlist(f.ticker).then(() => { refetchWatchlist(); refetch() })
                            }
                          }}
                          className="text-muted-foreground hover:text-primary transition-colors"
                        >
                          <Star className={cn("h-4 w-4", watchlist.includes(f.ticker) && "fill-primary text-primary")} />
                        </button>
                      )}
                      <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div className="rounded border border-border bg-secondary/50 p-2">
                      <p className="text-[10px] uppercase text-muted-foreground">{t("currentPrice")}</p>
                      <p className="font-mono text-sm font-semibold text-card-foreground">{formatCurrency(f.currentPrice, { currency: f.ticker })}</p>
                    </div>
                    <div className="rounded border border-border bg-secondary/50 p-2">
                      <p className="text-[10px] uppercase text-muted-foreground">{t("targetPrice")}</p>
                      <p className="font-mono text-sm font-semibold text-card-foreground">{formatCurrency(f.targetPrice, { currency: f.ticker })}</p>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                    <ConfidencePill value={f.confidence} />
                    <span className={cn("flex items-center gap-1 font-mono text-sm font-semibold", tone)}>
                      <Icon className="h-3.5 w-3.5" />
                      {formatPercent(f.expectedReturn)}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Sparkles className="h-3 w-3 text-primary" /> {f.model}
                    </span>
                    <span>
                      {f.horizonDays}d {t("horizon").toLowerCase()}
                    </span>
                  </div>
                </Link>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
