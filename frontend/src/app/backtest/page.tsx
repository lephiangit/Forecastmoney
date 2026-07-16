"use client"

import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { FlaskConical, Play, TrendingUp, TrendingDown, Target, BarChart3, Activity, Shield } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { formatCurrency, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { BacktestResult } from "@/lib/types"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts"

const PERIODS = [
  { value: 30, label: "30 days" },
  { value: 60, label: "60 days" },
  { value: 90, label: "90 days" },
  { value: 180, label: "6 months" },
  { value: 365, label: "1 year" },
]

const STRATEGIES = [
  { value: "conservative", label: "Conservative", color: "text-blue-400" },
  { value: "balanced", label: "Balanced", color: "text-primary" },
  { value: "aggressive", label: "Aggressive", color: "text-orange-400" },
]

export default function BacktestPage() {
  const t = useT()
  const [ticker, setTicker] = useState("BTC-USD")
  const [daysBack, setDaysBack] = useState(90)
  const [strategy, setStrategy] = useState("balanced")
  const [initialBalance, setInitialBalance] = useState(10000)
  const [tradeAmount, setTradeAmount] = useState(500)

  const mutation = useMutation({
    mutationFn: () =>
      api.runBacktest({ ticker, days_back: daysBack, strategy, initial_balance: initialBalance, trade_amount: tradeAmount }),
  })

  const result: BacktestResult | null | undefined = mutation.data

  return (
    <div>
      <PageHeader title={t("backtesting")} subtitle="Simulate AI strategies on historical data" />

      {/* Config Form */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg border border-border bg-card p-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">Ticker</label>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="BTC-USD"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">{t("period")}</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {PERIODS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">{t("strategy")}</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">{t("initialCapital")}</label>
            <input
              type="number"
              value={initialBalance}
              onChange={(e) => setInitialBalance(Number(e.target.value))}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !ticker}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {mutation.isPending ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {t("runBacktest")}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {result ? (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {/* Stats Cards */}
            <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard
                label={t("finalBalance")}
                value={result.summary.final_balance}
                format={formatCurrency}
                changePercent={result.summary.total_pnl_pct}
                icon={TrendingUp}
                accent
              />
              <StatCard
                label={t("winRate")}
                value={result.summary.win_rate}
                format={(n) => `${n.toFixed(1)}%`}
                icon={Target}
                delay={0.05}
              />
              <StatCard
                label={t("maxDrawdown")}
                value={result.summary.max_drawdown}
                format={(n) => `${n.toFixed(1)}%`}
                icon={Shield}
                delay={0.1}
              />
              <StatCard
                label={t("sharpeRatio")}
                value={result.summary.sharpe_ratio}
                format={(n) => n.toFixed(2)}
                icon={Activity}
                delay={0.15}
              />
            </div>

            {/* Equity Curve Chart */}
            <div className="mt-6 rounded-lg border border-border bg-card p-5">
              <h3 className="mb-4 font-semibold text-card-foreground">{t("equityCurve")}</h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={result.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(v: string) => v.slice(5)}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px" }}
                      labelStyle={{ color: "hsl(var(--foreground))" }}
                      formatter={(val: any) => [`$${Number(val).toLocaleString()}`, "Balance"]}
                    />
                    <ReferenceLine y={result.summary.initial_balance} stroke="hsl(var(--muted-foreground))" strokeDasharray="5 5" label="" />
                    <Line
                      type="monotone"
                      dataKey="balance"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Trade History Table */}
            <div className="mt-6 rounded-lg border border-border bg-card p-5">
              <h3 className="mb-4 font-semibold text-card-foreground">{t("tradeHistory")} ({result.trades.length})</h3>
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card">
                    <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                      <th className="pb-2 pr-3">Date</th>
                      <th className="pb-2 pr-3">Action</th>
                      <th className="pb-2 pr-3 text-right">{t("price")}</th>
                      <th className="pb-2 pr-3 text-right">{t("quantity")}</th>
                      <th className="pb-2 pr-3 text-right">Total</th>
                      <th className="pb-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((trade, idx) => (
                      <tr key={idx} className="border-b border-border/50 transition-colors hover:bg-accent/30">
                        <td className="py-2 pr-3 font-mono text-xs">{trade.date}</td>
                        <td className="py-2 pr-3">
                          <span className={cn(
                            "rounded px-1.5 py-0.5 text-xs font-semibold",
                            trade.action === "BUY" ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                          )}>
                            {trade.action}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right font-mono">{formatCurrency(trade.price, { currency: ticker })}</td>
                        <td className="py-2 pr-3 text-right font-mono">{trade.quantity}</td>
                        <td className="py-2 pr-3 text-right font-mono">{formatCurrency(trade.total)}</td>
                        <td className="py-2 text-xs text-muted-foreground max-w-[200px] truncate">{trade.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        ) : !mutation.isPending ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-12 flex flex-col items-center justify-center gap-3 text-center text-muted-foreground"
          >
            <FlaskConical className="h-12 w-12 opacity-40" />
            <p className="text-sm">{t("noBacktestResults")}</p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
