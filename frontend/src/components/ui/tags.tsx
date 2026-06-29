import { cn } from "@/lib/utils"

export function ActionBadge({ action }: { action: "BUY" | "SELL" | "HOLD" }) {
  const styles = {
    BUY: "bg-positive/15 text-positive border-positive/30",
    SELL: "bg-negative/15 text-negative border-negative/30",
    HOLD: "bg-muted-foreground/15 text-muted-foreground border-muted-foreground/30",
  }
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold", styles[action])}>
      {action}
    </span>
  )
}

export function SentimentBadge({ sentiment, label }: { sentiment: "bullish" | "bearish" | "neutral"; label: string }) {
  const styles = {
    bullish: "bg-positive/15 text-positive border-positive/30",
    bearish: "bg-negative/15 text-negative border-negative/30",
    neutral: "bg-info/15 text-info border-info/30",
  }
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold capitalize", styles[sentiment])}>
      {label}
    </span>
  )
}

export function ConfidencePill({ value }: { value: number }) {
  const v = Number(value) || 0
  const color = v >= 85 ? "text-positive" : v >= 70 ? "text-primary" : "text-muted-foreground"
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-accent">
        <div
          className={cn("h-full rounded-full", v >= 85 ? "bg-positive" : v >= 70 ? "bg-primary" : "bg-muted-foreground")}
          style={{ width: `${v}%` }}
        />
      </div>
      <span className={cn("font-mono text-xs font-semibold", color)}>{v.toFixed(0)}%</span>
    </div>
  )
}

export function StatusDot({ status }: { status: "healthy" | "warning" | "critical" | "active" | "suspended" }) {
  const color =
    status === "healthy" || status === "active"
      ? "bg-positive"
      : status === "warning"
        ? "bg-primary"
        : "bg-negative"
  return <span className={cn("inline-block h-2 w-2 rounded-full", color)} />
}
