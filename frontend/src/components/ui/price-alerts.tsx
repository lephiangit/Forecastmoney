"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Bell, BellRing, ChevronUp, ChevronDown, Trash2, Plus, Check } from "lucide-react"
import { api } from "@/lib/api"
import { useT, useAuthStore } from "@/lib/store"
import { formatCurrency } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { PriceAlert } from "@/lib/types"

interface PriceAlertsProps {
  defaultTicker?: string
  className?: string
}

export function PriceAlerts({ defaultTicker = "", className }: PriceAlertsProps) {
  const t = useT()
  const qc = useQueryClient()
  const { user } = useAuthStore()

  const [ticker, setTicker] = useState(defaultTicker)
  const [condition, setCondition] = useState<"above" | "below">("above")
  const [targetPrice, setTargetPrice] = useState("")
  const [showForm, setShowForm] = useState(false)
  const [created, setCreated] = useState(false)

  const { data: alerts = [] } = useQuery({
    queryKey: ["price-alerts"],
    queryFn: api.getPriceAlerts,
    enabled: !!user,
    refetchInterval: 15000,
  })

  const createMut = useMutation({
    mutationFn: () => api.createPriceAlert(ticker, condition, Number(targetPrice)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price-alerts"] })
      setTargetPrice("")
      setCreated(true)
      setTimeout(() => setCreated(false), 2000)
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deletePriceAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["price-alerts"] }),
  })

  const active = alerts.filter((a: PriceAlert) => !a.is_triggered)
  const triggered = alerts.filter((a: PriceAlert) => a.is_triggered)

  if (!user) return null

  return (
    <div className={cn("rounded-lg border border-border bg-card p-5", className)}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-card-foreground">{t("priceAlerts")}</h3>
          {active.length > 0 && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{active.length}</span>
          )}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1 rounded-md border border-primary/40 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/10"
        >
          <Plus className="h-3 w-3" />
          {t("createAlert")}
        </button>
      </div>

      {/* Create Alert Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mb-4 overflow-hidden"
          >
            <div className="flex flex-wrap items-end gap-3 rounded-md border border-border/50 bg-background p-3">
              <div className="min-w-[100px] flex-1">
                <label className="mb-1 block text-xs text-muted-foreground">Ticker</label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="BTC-USD"
                  className="flex h-9 w-full rounded-md border border-input bg-card px-3 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <div className="min-w-[90px]">
                <label className="mb-1 block text-xs text-muted-foreground">Condition</label>
                <select
                  value={condition}
                  onChange={(e) => setCondition(e.target.value as "above" | "below")}
                  className="flex h-9 w-full rounded-md border border-input bg-card px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="above">{t("alertAbove")} ▲</option>
                  <option value="below">{t("alertBelow")} ▼</option>
                </select>
              </div>
              <div className="min-w-[120px] flex-1">
                <label className="mb-1 block text-xs text-muted-foreground">{t("targetPriceLabel")}</label>
                <input
                  type="number"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  placeholder="70000"
                  className="flex h-9 w-full rounded-md border border-input bg-card px-3 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <button
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending || !ticker || !targetPrice}
                className="flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {created ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                {created ? t("alertCreated") : t("createAlert")}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Active Alerts */}
      {active.length === 0 && triggered.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">{t("noAlerts")}</p>
      ) : (
        <div className="space-y-2">
          {active.map((alert: PriceAlert) => (
            <motion.div
              key={alert.id}
              layout
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              className="flex items-center justify-between rounded-md border border-border/50 bg-background px-3 py-2"
            >
              <div className="flex items-center gap-2.5">
                <Bell className="h-4 w-4 text-muted-foreground" />
                <span className="font-mono text-sm font-semibold">{alert.ticker}</span>
                <span className={cn(
                  "flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-semibold",
                  alert.condition === "above" ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                )}>
                  {alert.condition === "above" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  {alert.condition === "above" ? t("alertAbove") : t("alertBelow")}
                </span>
                <span className="font-mono text-sm">{formatCurrency(alert.target_price)}</span>
              </div>
              <button
                onClick={() => deleteMut.mutate(alert.id)}
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          ))}

          {/* Triggered alerts */}
          {triggered.map((alert: PriceAlert) => (
            <motion.div
              key={alert.id}
              layout
              className="flex items-center justify-between rounded-md border border-primary/30 bg-primary/5 px-3 py-2"
            >
              <div className="flex items-center gap-2.5">
                <BellRing className="h-4 w-4 text-primary" />
                <span className="font-mono text-sm font-semibold">{alert.ticker}</span>
                <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary">
                  {t("alertTriggered")} ✓
                </span>
                <span className="font-mono text-sm text-muted-foreground">{formatCurrency(alert.target_price)}</span>
              </div>
              <button
                onClick={() => deleteMut.mutate(alert.id)}
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
