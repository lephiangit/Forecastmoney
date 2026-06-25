"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Wallet, TrendingUp, DollarSign, PieChart, ArrowUpRight } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { SignalCard } from "@/components/features/signal-card"
import { PortfolioChart } from "@/components/dashboard/portfolio-chart"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { Sparkline } from "@/components/ui/sparkline"
import { formatCurrency, formatPercent, timeAgo } from "@/lib/format"
import { ActionBadge } from "@/components/ui/tags"
import { cn } from "@/lib/utils"

export default function DashboardPage() {
  const t = useT()
  const portfolioQ = useQuery({ queryKey: ["portfolio"], queryFn: api.getPortfolio })
  const signalsQ = useQuery({ queryKey: ["signals"], queryFn: api.getSignals })
  const txQ = useQuery({ queryKey: ["transactions"], queryFn: api.getTransactions })
  const marketsQ = useQuery({ queryKey: ["markets"], queryFn: api.getMarkets, refetchInterval: 30000 })

  const p = portfolioQ.data

  return (
    <div>
      <PageHeader title={t("accountOverview")} subtitle={t("howIsMyAccount")} />

      {portfolioQ.isError ? (
        <ErrorCard onRetry={() => portfolioQ.refetch()} />
      ) : !p ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label={t("totalValue")} value={p.totalValue} format={(n) => formatCurrency(n)} changePercent={p.dayPnlPercent} icon={Wallet} accent delay={0} />
          <StatCard label={t("todayPnl")} value={p.dayPnl} format={(n) => formatCurrency(n)} changePercent={p.dayPnlPercent} icon={TrendingUp} delay={0.05} />
          <StatCard label={t("totalPnl")} value={p.totalPnl} format={(n) => formatCurrency(n)} changePercent={p.totalPnlPercent} icon={PieChart} delay={0.1} />
          <StatCard label={t("availableCash")} value={p.cash} format={(n) => formatCurrency(n)} icon={DollarSign} delay={0.15} />
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-border bg-card p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-card-foreground">{t("portfolioPerformance")}</h2>
              <Link href="/portfolio" className="flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                {t("viewAll")} <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
            {portfolioQ.isError ? (
              <ErrorCard onRetry={() => portfolioQ.refetch()} />
            ) : !p ? (
              <Skeleton className="h-64" />
            ) : (
              <PortfolioChart data={p.history} />
            )}
          </div>

          <div className="mt-6 rounded-lg border border-border bg-card p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-card-foreground">{t("myHoldings")}</h2>
              <Link href="/portfolio" className="text-xs font-medium text-primary hover:underline">{t("viewAll")}</Link>
            </div>
            {!p ? (
              <Skeleton className="h-40" />
            ) : (
              <div className="space-y-1">
                {p.holdings.map((h) => {
                  const pos = h.unrealizedPnl >= 0
                  return (
                    <Link
                      key={h.ticker}
                      href={`/forecast/${h.ticker}`}
                      className="flex items-center justify-between rounded-md px-2 py-2.5 transition-colors hover:bg-accent/50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                          {h.ticker.slice(0, 3)}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-card-foreground">{h.ticker}</p>
                          <p className="text-xs text-muted-foreground">{h.quantity} units</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-mono text-sm text-card-foreground">{formatCurrency(h.marketValue)}</p>
                        <p className={cn("font-mono text-xs", pos ? "text-positive" : "text-negative")}>{formatPercent(h.unrealizedPnlPercent)}</p>
                      </div>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <h2 className="mb-3 font-semibold text-card-foreground">{t("topSignals")}</h2>
            {signalsQ.isError ? (
              <ErrorCard onRetry={() => signalsQ.refetch()} />
            ) : !signalsQ.data ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
              </div>
            ) : (
              <div className="space-y-3">
                {signalsQ.data.slice(0, 3).map((s, i) => (
                  <SignalCard key={s.id} signal={s} index={i} />
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 font-semibold text-card-foreground">{t("recentActivity")}</h2>
            {!txQ.data ? (
              <Skeleton className="h-32" />
            ) : (
              <div className="space-y-2.5">
                {txQ.data.slice(0, 5).map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <ActionBadge action={tx.action} />
                      <span className="font-mono font-medium text-card-foreground">{tx.ticker}</span>
                      {tx.source === "auto" && (
                        <span className="rounded bg-info/15 px-1.5 py-0.5 text-[10px] font-semibold text-info">AUTO</span>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-xs text-card-foreground">{formatCurrency(tx.total)}</p>
                      <p className="text-[10px] text-muted-foreground">{timeAgo(tx.createdAt)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-card-foreground">{t("marketSnapshot")}</h2>
          <Link href="/markets" className="text-xs font-medium text-primary hover:underline">{t("viewAll")}</Link>
        </div>
        {!marketsQ.data ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            {marketsQ.data.slice(0, 5).map((a, i) => {
              const pos = a.changePercent >= 0
              return (
                <motion.div
                  key={a.ticker}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link href={`/forecast/${a.ticker}`} className="block rounded-lg border border-border bg-card p-3 transition-colors hover:border-muted-foreground/40">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm font-bold text-card-foreground">{a.ticker}</span>
                      <span className={cn("font-mono text-xs", pos ? "text-positive" : "text-negative")}>{formatPercent(a.changePercent)}</span>
                    </div>
                    <p className="mt-1 font-mono text-sm text-card-foreground">{formatCurrency(a.price)}</p>
                    <div className="mt-2">
                      <Sparkline data={a.sparkline} positive={pos} width={140} height={32} />
                    </div>
                  </Link>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
