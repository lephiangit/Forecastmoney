"use client"

import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Bot, Play, Square, Target, Percent, Shield, TrendingUp, Activity, Save, Check, Clock, DollarSign } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import type { AutoTradeConfig } from "@/lib/types"
import type { TranslationKey } from "@/lib/i18n"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { formatCurrency } from "@/lib/format"
import { cn } from "@/lib/utils"

const STRATEGIES: { value: AutoTradeConfig["strategy"]; key: TranslationKey; desc: string }[] = [
  { value: "conservative", key: "conservative", desc: "Low risk, smaller positions, high-confidence signals only." },
  { value: "balanced", key: "balanced", desc: "Moderate risk with a mix of momentum and value signals." },
  { value: "aggressive", key: "aggressive", desc: "Higher risk, larger positions, faster signal execution." },
]

const TRADEABLE = ["BTC", "ETH", "NVDA", "AAPL", "TSLA", "SP500", "GOLD"]

const DEFAULT_CONFIG: AutoTradeConfig = {
  enabled: false,
  strategy: "balanced",
  maxPositionSize: 15,
  minConfidence: 75,
  assets: ["BTC", "ETH", "NVDA"],
  stopLoss: 5,
  takeProfit: 15,
}

export default function AutoTradePage() {
  const queryClient = useQueryClient()
  const t = useT()
  const statsQ = useQuery({ queryKey: ["autoTradeStats"], queryFn: api.getAutoTradeStats, refetchInterval: 15000 })
  const portfolioQ = useQuery({ queryKey: ["portfolio"], queryFn: api.getPortfolio, refetchInterval: 15000 })
  const txQ = useQuery({ queryKey: ["transactions"], queryFn: api.getTransactions, refetchInterval: 15000 })
  const botConfigQ = useQuery({ queryKey: ["botConfig"], queryFn: api.getBotConfig })
  const watchlistQ = useQuery({ queryKey: ["watchlist"], queryFn: api.getWatchlist })

  const [config, setConfig] = useState<AutoTradeConfig>(DEFAULT_CONFIG)
  const [saved, setSaved] = useState(false)
  const [tradeAmount, setTradeAmount] = useState<number | string>(500)
  const [durationHours, setDurationHours] = useState<number | string>(24)

  const isBotRunning = portfolioQ.data?.is_running || false

  useEffect(() => {
    if (botConfigQ.data) {
      setTradeAmount(botConfigQ.data.amount || 500)
    }
  }, [botConfigQ.data])

  const startMut = useMutation({
    mutationFn: () => api.startBotAdvanced({
      amount: Number(tradeAmount) || 0,
      duration_hours: Number(durationHours) || 0,
      assets: config.assets,
      strategy: config.strategy,
      stop_loss: config.stopLoss,
      take_profit: config.takeProfit,
      min_confidence: config.minConfidence,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] })
      queryClient.invalidateQueries({ queryKey: ["botConfig"] })
    }
  })

  const stopMut = useMutation({
    mutationFn: () => api.stopBot(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] })
      queryClient.invalidateQueries({ queryKey: ["botConfig"] })
    }
  })

  useEffect(() => {
    // config state is already initialized
  }, [])

  function update<K extends keyof AutoTradeConfig>(key: K, value: AutoTradeConfig[K]) {
    setConfig((c) => ({ ...c, [key]: value }))
    setSaved(false)
  }

  function toggleAsset(ticker: string) {
    const assets = config.assets.includes(ticker)
      ? config.assets.filter((a) => a !== ticker)
      : [...config.assets, ticker]
    update("assets", assets)
  }

  const stats = statsQ.data

  return (
    <div>
      <PageHeader title={t("autoTrading")} subtitle={t("whatAiTrades")} />

      {!config ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          {/* Bot status / Start-Stop */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "flex flex-col gap-4 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between",
              isBotRunning ? "border-positive/40" : "border-border",
            )}
          >
            <div className="flex items-center gap-4">
              <div
                className={cn(
                  "relative flex h-12 w-12 items-center justify-center rounded-lg",
                  isBotRunning ? "bg-positive/15 text-positive" : "bg-accent text-muted-foreground",
                )}
              >
                <Bot className="h-6 w-6" />
                {isBotRunning && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-positive opacity-75" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-positive" />
                  </span>
                )}
              </div>
              <div>
                <h2 className="font-semibold text-card-foreground">
                  Trading Bot {isBotRunning ? "Running" : "Stopped"}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {isBotRunning
                    ? `Executing the ${t(config.strategy)} strategy across ${config.assets.length} assets.`
                    : "Bot is idle. Configure and start to begin automated trading."}
                </p>
              </div>
            </div>
            <button
              onClick={() => isBotRunning ? stopMut.mutate() : startMut.mutate()}
              disabled={startMut.isPending || stopMut.isPending}
              className={cn(
                "flex items-center justify-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-50",
                isBotRunning
                  ? "bg-negative text-primary-foreground"
                  : "bg-positive text-primary-foreground",
              )}
            >
              {isBotRunning ? (
                <>
                  <Square className="h-4 w-4" /> Stop Bot
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" /> Start Bot
                </>
              )}
            </button>
          </motion.div>

          {/* Trade Settings */}
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="font-semibold text-card-foreground">Cấu hình Ngân sách & Thời gian</h3>
              <div className="mt-4 space-y-5">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-card-foreground flex items-center gap-2">
                    <DollarSign className="w-4 h-4" /> Số tiền mỗi lệnh giao dịch ($)
                  </label>
                  <input
                    type="number"
                    value={tradeAmount}
                    onChange={(e) => {
                      const val = e.target.value.replace(/^0+(?=\d)/, "");
                      setTradeAmount(val);
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <p className="text-xs text-muted-foreground">Số lượng coin mua sẽ phụ thuộc vào giá thực tế lúc Trade.</p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-card-foreground flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Thời lượng Trade (Giờ)
                  </label>
                  <input
                    type="number"
                    value={durationHours}
                    onChange={(e) => {
                      const val = e.target.value.replace(/^0+(?=\d)/, "");
                      setDurationHours(val);
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <p className="text-xs text-muted-foreground">
                    {botConfigQ.data?.end_time && isBotRunning 
                      ? `Bot sẽ tự động dừng vào: ${new Date(botConfigQ.data.end_time).toLocaleString()}`
                      : "Bot sẽ tự động dừng sau khoảng thời gian này."}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {!stats ? (
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
            ) : (
              <>
                <StatCard label={t("winRate")} value={stats.winRate ?? 0} format={(n) => `${(Number(n) || 0).toFixed(1)}%`} icon={Target} accent />
                <StatCard label={t("totalTrades")} value={stats.totalTrades ?? 0} format={(n) => (Number(n) || 0).toFixed(0)} icon={Activity} delay={0.05} />
                <StatCard label="Bot P&L" value={stats.pnl ?? 0} format={(n) => formatCurrency(n)} changePercent={stats.totalReturn ?? 0} icon={TrendingUp} delay={0.1} />
                <StatCard label={t("activePositions")} value={stats.activePositions ?? 0} format={(n) => (Number(n) || 0).toFixed(0)} icon={Shield} delay={0.15} />
              </>
            )}
          </div>

          {/* Configuration */}
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="font-semibold text-card-foreground">{t("strategy")}</h3>
              <div className="mt-4 space-y-2.5">
                {STRATEGIES.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => update("strategy", s.value)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors",
                      config.strategy === s.value
                        ? "border-primary/60 bg-primary/5"
                        : "border-border bg-secondary hover:bg-accent",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border",
                        config.strategy === s.value ? "border-primary bg-primary" : "border-muted-foreground",
                      )}
                    >
                      {config.strategy === s.value && <span className="h-1.5 w-1.5 rounded-full bg-primary-foreground" />}
                    </span>
                    <span>
                      <span className="block text-sm font-semibold capitalize text-card-foreground">{t(s.key)}</span>
                      <span className="block text-xs text-muted-foreground">{s.desc}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="font-semibold text-card-foreground">Risk Parameters</h3>
              <div className="mt-4 space-y-5">
                <SliderRow icon={Percent} label={t("maxPositionSize")} value={config.maxPositionSize} suffix="%" min={5} max={50} onChange={(v) => update("maxPositionSize", v)} />
                <SliderRow icon={Target} label={t("minConfidence")} value={config.minConfidence} suffix="%" min={50} max={95} onChange={(v) => update("minConfidence", v)} />
                <SliderRow icon={Shield} label={t("stopLoss")} value={config.stopLoss} suffix="%" min={2} max={25} onChange={(v) => update("stopLoss", v)} />
                <SliderRow icon={TrendingUp} label={t("takeProfit")} value={config.takeProfit} suffix="%" min={5} max={50} onChange={(v) => update("takeProfit", v)} />
              </div>
            </div>
          </div>

          {/* Traded assets */}
          <div className="mt-6 rounded-lg border border-border bg-card p-5">
            <h3 className="font-semibold text-card-foreground">{t("tradedAssets")}</h3>
            <div className="mt-4 flex flex-wrap gap-2">
              {(() => {
                const watchlist = watchlistQ.data || []
                const displayAssets = Array.from(new Set([...watchlist, ...TRADEABLE]))
                  .sort((a, b) => {
                    const aWatch = watchlist.includes(a)
                    const bWatch = watchlist.includes(b)
                    if (aWatch && !bWatch) return -1
                    if (!aWatch && bWatch) return 1
                    return 0
                  })

                return displayAssets.map((ticker) => {
                  const active = config.assets.includes(ticker)
                  return (
                    <button
                      key={ticker}
                      onClick={() => toggleAsset(ticker)}
                      className={cn(
                        "flex items-center gap-1.5 rounded-md border px-3 py-1.5 font-mono text-sm font-semibold transition-colors",
                        active
                          ? "border-primary/60 bg-primary/10 text-primary"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {active && <Check className="h-3.5 w-3.5" />}
                      {ticker}
                    </button>
                  )
                })
              })()}
            </div>
          </div>

          <div className="mt-6 flex items-center justify-end gap-3">
            <AnimatePresence>
              {saved && (
                <motion.span
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-1.5 text-sm text-positive"
                >
                  <Check className="h-4 w-4" /> Configuration saved
                </motion.span>
              )}
            </AnimatePresence>
            <button
              onClick={() => setSaved(true)}
              className="flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              <Save className="h-4 w-4" /> {t("saveConfig")}
            </button>
          </div>
          
          {/* Portfolio & History */}
          {portfolioQ.data && (
            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              {/* Positions */}
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="font-semibold text-card-foreground">Vị thế đang mở (Open Positions)</h3>
                <div className="mt-4 space-y-3">
                  {portfolioQ.data.holdings.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Không có vị thế nào.</p>
                  ) : (
                    portfolioQ.data.holdings.map((h) => (
                      <div key={h.ticker} className="flex justify-between rounded-md border border-border bg-secondary p-3">
                        <div>
                          <span className="block font-bold text-card-foreground">{h.ticker}</span>
                          <span className="block text-xs text-muted-foreground">SL: {h.quantity}</span>
                        </div>
                        <div className="text-right">
                          <span className="block font-mono text-sm text-card-foreground">{formatCurrency(h.avgPrice, { currency: h.ticker })}</span>
                          <span className="block text-xs text-muted-foreground">Giá vốn</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* History */}
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="font-semibold text-card-foreground">Lịch sử giao dịch (Trade History)</h3>
                <div className="mt-4 space-y-3 max-h-80 overflow-y-auto pr-2">
                  {!txQ.data || txQ.data.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Chưa có giao dịch.</p>
                  ) : (
                    txQ.data.map((trade, idx) => (
                      <div key={trade.id || idx} className="flex justify-between rounded-md border border-border bg-secondary p-3">
                        <div className="flex flex-col">
                          <span className="font-bold text-card-foreground">{trade.ticker} <span className={cn("text-xs px-1.5 py-0.5 rounded ml-2", trade.action === "BUY" ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative")}>{trade.action}</span></span>
                          <span className="text-xs text-muted-foreground mt-1">{new Date(trade.createdAt).toLocaleString()}</span>
                        </div>
                        <div className="text-right flex flex-col justify-center">
                          <span className="font-mono text-sm text-card-foreground">{formatCurrency(trade.price, { currency: trade.ticker })}</span>
                          <span className="text-xs text-muted-foreground">x{trade.quantity}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function SliderRow({
  icon: Icon,
  label,
  value,
  suffix,
  min,
  max,
  onChange,
}: {
  icon: typeof Percent
  label: string
  value: number
  suffix: string
  min: number
  max: number
  onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          <Icon className="h-4 w-4" /> {label}
        </span>
        <span className="font-mono text-sm font-semibold text-card-foreground">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary"
      />
    </div>
  )
}
