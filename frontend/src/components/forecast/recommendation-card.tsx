import { Clock } from "lucide-react"
import type { Asset, Kpis, Research } from "@/lib/forecast-data"
import { formatPrice } from "@/lib/forecast-data"
import { cn } from "@/lib/utils"

const STYLES = {
  BUY: { badge: "bg-up text-background", text: "text-up", ring: "border-up/40" },
  HOLD: {
    badge: "bg-primary text-primary-foreground",
    text: "text-primary",
    ring: "border-primary/40",
  },
  SELL: {
    badge: "bg-down text-background",
    text: "text-down",
    ring: "border-down/40",
  },
} as const

export function RecommendationCard({
  asset,
  kpis,
  research,
}: {
  asset: Asset
  kpis: Kpis
  research: Research
}) {
  const style = STYLES[research.recommendation]
  const generated = new Date(research.generatedAt).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  })

  return (
    <aside
      className={cn(
        "sticky top-4 rounded-xl border bg-card p-5",
        style.ring,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        AI Recommendation
      </p>

      <div className="mt-3 flex items-center gap-3">
        <span
          className={cn(
            "rounded-lg px-4 py-2 text-2xl font-bold tracking-tight",
            style.badge,
          )}
        >
          {research.recommendation}
        </span>
        <span className={cn("text-sm font-medium", style.text)}>
          {kpis.confidence}% confidence
        </span>
      </div>

      <dl className="mt-5 space-y-3 border-t border-border pt-4 text-sm">
        <Row label="Target Price">
          {formatPrice(kpis.targetPrice, asset)}
        </Row>
        <Row label="Expected Return">
          <span className={kpis.expectedReturn >= 0 ? "text-up" : "text-down"}>
            {kpis.expectedReturn >= 0 ? "+" : ""}
            {kpis.expectedReturn}%
          </span>
        </Row>
        <Row label="Risk Level">{kpis.riskLevel}</Row>
        <Row label="Time Horizon">{research.timeHorizon}</Row>
      </dl>

      <p className="mt-4 flex items-center gap-1.5 border-t border-border pt-3 text-xs text-muted-foreground">
        <Clock className="size-3.5" />
        Generated {generated}
      </p>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        For research purposes only. Not financial advice.
      </p>
    </aside>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono font-medium tabular-nums">{children}</dd>
    </div>
  )
}
