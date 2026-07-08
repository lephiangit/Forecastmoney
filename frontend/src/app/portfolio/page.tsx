"use client"

import { useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from "recharts"
import { Wallet, TrendingUp, PieChart as PieChartIcon, DollarSign } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { PortfolioChart } from "@/components/dashboard/portfolio-chart"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { ActionBadge } from "@/components/ui/tags"
import { formatCurrency, formatPercent, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const ALLOC_COLORS = ["#fcd535", "#0ecb81", "#3861fb", "#f6465d", "#a78bfa"]

export default function PortfolioPage() {
  const t = useT()
  const portfolioQ = useQuery({ queryKey: ["portfolio"], queryFn: api.getPortfolio, refetchInterval: 5000 })
  const txQ = useQuery({ queryKey: ["transactions"], queryFn: api.getTransactions, refetchInterval: 5000 })
  const [tab, setTab] = useState<"holdings" | "transactions">("holdings")
  const p = portfolioQ.data

  return (
    <div>
      <PageHeader title={t("portfolioManagement")} subtitle={t("whatIOwn")} />

      {portfolioQ.isError ? (
        <ErrorCard onRetry={() => portfolioQ.refetch()} />
      ) : !p ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label={t("totalValue")} value={p.totalValue} format={(n) => formatCurrency(n)} changePercent={p.dayPnlPercent} icon={Wallet} accent />
            <StatCard label={t("totalPnl")} value={p.totalPnl} format={(n) => formatCurrency(n)} changePercent={p.totalPnlPercent} icon={TrendingUp} delay={0.05} />
            <StatCard label={t("allocation")} value={p.investedValue} format={(n) => formatCurrency(n)} icon={PieChartIcon} delay={0.1} />
            <StatCard label={t("availableCash")} value={p.cash} format={(n) => formatCurrency(n)} icon={DollarSign} delay={0.15} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-lg border border-border bg-card p-4 sm:p-5 lg:col-span-2">
              <h2 className="mb-4 font-semibold text-card-foreground">{t("portfolioPerformance")}</h2>
              <PortfolioChart data={p.history} />
            </div>

            <div className="rounded-lg border border-border bg-card p-4 sm:p-5">
              <h2 className="mb-4 font-semibold text-card-foreground">{t("allocation")}</h2>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
                <div className="h-48 w-48 relative">
                  {p.holdings.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={p.holdings}
                          dataKey="allocation"
                          nameKey="ticker"
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={80}
                          paddingAngle={2}
                          stroke="none"
                        >
                          {p.holdings.map((h, i) => (
                            <Cell key={h.ticker} fill={ALLOC_COLORS[i % ALLOC_COLORS.length]} />
                          ))}
                        </Pie>
                        <RechartsTooltip 
                          formatter={(value: any) => `${Number(value).toFixed(1)}%`}
                          contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                          itemStyle={{ color: 'hsl(var(--foreground))' }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center rounded-full border-4 border-dashed border-border text-xs text-muted-foreground">
                      No Assets
                    </div>
                  )}
                </div>
                
                <div className="space-y-3 flex-1 w-full">
                  {p.holdings.map((h, i) => (
                    <div key={h.ticker} className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 font-medium text-card-foreground">
                        <span className="h-3 w-3 rounded-sm" style={{ background: ALLOC_COLORS[i % ALLOC_COLORS.length] }} />
                        {h.ticker}
                      </span>
                      <span className="font-mono text-muted-foreground">{(Number(h.allocation) || 0).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Holdings / Transactions tabs */}
          <div className="mt-6">
            <div className="mb-4 inline-flex overflow-hidden rounded-md border border-border">
              {(["holdings", "transactions"] as const).map((tb) => (
                <button
                  key={tb}
                  onClick={() => setTab(tb)}
                  className={cn(
                    "px-4 py-2 text-sm font-medium transition-colors",
                    tab === tb ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
                  )}
                >
                  {tb === "holdings" ? t("holdings") : t("transactions")}
                </button>
              ))}
            </div>

            {tab === "holdings" ? (
              <div className="overflow-x-auto rounded-lg border border-border bg-card">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-3 font-medium">{t("asset")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("quantity")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("avgCost")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("price")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("marketValue")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("unrealizedPnl")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.holdings.map((h, i) => {
                      const pos = h.unrealizedPnl >= 0
                      return (
                        <motion.tr
                          key={h.ticker}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: i * 0.04 }}
                          className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40"
                        >
                          <td className="px-4 py-3">
                            <Link href={`/forecast/${h.ticker}`} className="flex items-center gap-3">
                              <span className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                                {h.ticker.slice(0, 3)}
                              </span>
                              <div>
                                <p className="font-mono font-semibold text-card-foreground">{h.ticker}</p>
                                <p className="text-xs text-muted-foreground">{h.name}</p>
                              </div>
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-muted-foreground">{h.quantity}</td>
                          <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(h.avgPrice, { currency: h.ticker })}</td>
                          <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(h.currentPrice, { currency: h.ticker })}</td>
                          <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(h.marketValue, { currency: h.ticker })}</td>
                          <td className="px-4 py-3 text-right">
                            <span className={cn("font-mono font-medium", pos ? "text-positive" : "text-negative")}>
                              {formatCurrency(h.unrealizedPnl, { currency: h.ticker })}
                            </span>
                            <p className={cn("font-mono text-xs", pos ? "text-positive" : "text-negative")}>
                              {formatPercent(h.unrealizedPnlPercent)}
                            </p>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-border bg-card">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-3 font-medium">{t("trade")}</th>
                      <th className="px-4 py-3 font-medium">{t("asset")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("quantity")}</th>
                      <th className="px-4 py-3 text-right font-medium">{t("price")}</th>
                      <th className="px-4 py-3 text-right font-medium">Total</th>
                      <th className="px-4 py-3 text-right font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(txQ.data ?? []).map((tx, i) => (
                      <motion.tr
                        key={tx.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.04 }}
                        className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <ActionBadge action={tx.action} />
                            {tx.source === "auto" && (
                              <span className="rounded bg-info/15 px-1.5 py-0.5 text-[10px] font-semibold text-info">AUTO</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono font-semibold text-card-foreground">{tx.ticker}</td>
                        <td className="px-4 py-3 text-right font-mono text-muted-foreground">{tx.quantity}</td>
                        <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(tx.price, { currency: tx.ticker })}</td>
                        <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(tx.total, { currency: tx.ticker })}</td>
                        <td className="px-4 py-3 text-right text-xs text-muted-foreground">{timeAgo(tx.createdAt)}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
