import { Activity, Gauge, ShieldAlert, Target } from "lucide-react"
import type { Asset, Kpis } from "@/lib/forecast-data"
import { formatPrice } from "@/lib/forecast-data"
import { cn } from "@/lib/utils"

function confidenceColor(confidence: number) {
  if (confidence > 80) return "text-up"
  if (confidence >= 60) return "text-primary"
  return "text-down"
}

function riskColor(risk: Kpis["riskLevel"]) {
  if (risk === "Low") return "text-up"
  if (risk === "Medium") return "text-primary"
  return "text-down"
}

export function KpiCards({ asset, kpis }: { asset: Asset; kpis: Kpis }) {
  const returnUp = kpis.expectedReturn >= 0

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card
        icon={<Activity className="size-4" />}
        label="Expected Return"
        value={`${returnUp ? "+" : ""}${kpis.expectedReturn}%`}
        valueClass={returnUp ? "text-up" : "text-down"}
      />
      <Card
        icon={<Target className="size-4" />}
        label="Target Price"
        value={formatPrice(kpis.targetPrice, asset)}
      />
      <Card
        icon={<Gauge className="size-4" />}
        label="Confidence"
        value={`${kpis.confidence}%`}
        valueClass={confidenceColor(kpis.confidence)}
      />
      <Card
        icon={<ShieldAlert className="size-4" />}
        label="Risk Level"
        value={kpis.riskLevel}
        valueClass={riskColor(kpis.riskLevel)}
      />
    </div>
  )
}

function Card({
  icon,
  label,
  value,
  valueClass,
}: {
  icon: React.ReactNode
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p
        className={cn(
          "mt-2 font-mono text-xl font-semibold tabular-nums sm:text-2xl",
          valueClass,
        )}
      >
        {value}
      </p>
    </div>
  )
}
