"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { ArrowLeft, Sparkles, TrendingUp, TrendingDown } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { formatCurrency, formatPercent } from "@/lib/format"
import { PageHeader } from "@/components/ui/page-header"
import { ForecastChart } from "@/components/charts/forecast-chart"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { ConfidencePill } from "@/components/ui/tags"
import { CountUp } from "@/components/ui/count-up"
import { cn } from "@/lib/utils"
import { TechnicalChart } from "@/components/charts/technical-chart"
import { PriceAlerts } from "@/components/ui/price-alerts"


export default function ForecastPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = use(params)
  const ticker = decodeURIComponent(symbol).toUpperCase()
  const t = useT()

  const forecastQ = useQuery({ queryKey: ["forecast", ticker], queryFn: () => api.getForecast(ticker) })
  const f = forecastQ.data

  return (
    <div>
      <Link
        href="/markets"
        className="mb-4 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("markets")}
      </Link>

      {forecastQ.isError ? (
        <ErrorCard onRetry={() => forecastQ.refetch()} />
      ) : !f ? (
        <div className="space-y-6">
          <Skeleton className="h-16" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <Skeleton className="h-80" />
        </div>
      ) : (
        <>
          <PageHeader
            title={`${f.ticker} — ${f.name}`}
            subtitle={`${t("aiPrediction")} · ${f.model}`}
            action={
              <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
                <span className="text-xs text-muted-foreground">{t("price")}</span>
                <span className="font-mono text-lg font-semibold text-card-foreground">
                  {formatCurrency(f.currentPrice, { currency: f.ticker })}
                </span>
              </div>
            }
          />

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricTile label={t("targetPrice")} value={formatCurrency(f.targetPrice, { currency: f.ticker })} />
            <MetricTile
              label={t("expectedReturn")}
              value={formatPercent(f.expectedReturn)}
              positive={f.expectedReturn >= 0}
              icon
            />
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("confidence")}</p>
              <div className="mt-3">
                <ConfidencePill value={f.confidence} />
              </div>
            </div>
            <MetricTile label={t("horizon")} value={`${f.horizonDays}d`} />
          </div>

          <section className="mt-6 rounded-lg border border-border bg-card p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h2 className="font-semibold text-card-foreground">{t("priceForecast")}</h2>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <Legend color="#eaecef" label={t("historical")} />
                <Legend color={f.direction === "down" ? "#f6465d" : "#0ecb81"} label={t("predicted")} dashed />
                <Legend color="rgba(56,97,251,0.5)" label={t("confidenceBand")} />
              </div>
            </div>
            <ForecastChart forecast={f} />
          </section>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <section className="lg:col-span-2 rounded-lg border border-border bg-card p-4 sm:p-5">
              <h2 className="mb-4 font-semibold text-card-foreground flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                {t("technicalAnalysis")}
              </h2>
              <TechnicalChart ticker={ticker} />
            </section>
            
            <div className="space-y-6">
              <PriceAlerts defaultTicker={ticker} />
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <SummaryCard
              label={t("aiPrediction")}
              value={f.direction === "up" ? t("bullish") : f.direction === "down" ? t("bearish") : t("neutral")}
              tone={f.direction}
            />
            <SummaryCard label={t("model")} value={f.model} />
            <SummaryCard label={t("updated")} value={new Date(f.updatedAt).toLocaleString()} />
          </div>
        </>
      )}
    </div>
  )
}

function MetricTile({
  label,
  value,
  positive,
  icon,
}: {
  label: string
  value: string
  positive?: boolean
  icon?: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-2 flex items-center gap-1 font-mono text-xl font-semibold tabular-nums",
          positive === undefined ? "text-card-foreground" : positive ? "text-positive" : "text-negative",
        )}
      >
        {icon && positive !== undefined && (positive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />)}
        {value}
      </p>
    </div>
  )
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" | "neutral" }) {
  const color = tone === "up" ? "text-positive" : tone === "down" ? "text-negative" : "text-card-foreground"
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-2 font-semibold", color)}>{value}</p>
    </div>
  )
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block h-0.5 w-4 rounded"
        style={{ background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 7px)` : color }}
      />
      {label}
    </span>
  )
}
