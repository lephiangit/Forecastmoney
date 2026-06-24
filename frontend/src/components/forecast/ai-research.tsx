import {
  Check,
  FileText,
  Newspaper,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react"
import type { Asset, Research } from "@/lib/forecast-data"

export function AiResearch({
  asset,
  research,
}: {
  asset: Asset
  research: Research
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-primary" />
        <h2 className="text-base font-semibold">AI Research</h2>
      </div>

      {/* Executive summary */}
      <Panel title="Executive Summary" icon={<FileText className="size-4" />}>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {research.summary}
        </p>
      </Panel>

      <div className="grid gap-3 md:grid-cols-2">
        <FactorPanel
          title="Bullish Factors"
          tone="up"
          icon={<TrendingUp className="size-4" />}
          items={research.bullish}
        />
        <FactorPanel
          title="Bearish Factors"
          tone="down"
          icon={<TrendingDown className="size-4" />}
          items={research.bearish}
        />
      </div>

      {/* News sentiment */}
      <Panel title="News Sentiment" icon={<Newspaper className="size-4" />}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-2xl font-semibold">
              {research.newsSentiment.label}
            </p>
            <p className="text-xs text-muted-foreground">
              Aggregated from {research.newsSentiment.sources} sources for{" "}
              {asset.name}
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-2xl font-semibold tabular-nums text-primary">
              {research.newsSentiment.score}
            </p>
            <p className="text-xs text-muted-foreground">/ 100</p>
          </div>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${research.newsSentiment.score}%` }}
          />
        </div>
      </Panel>
    </div>
  )
}

function Panel({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <details
      open
      className="group rounded-xl border border-border bg-card p-4 sm:p-5 [&[open]>summary_.chev]:rotate-180"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium [&::-webkit-details-marker]:hidden">
        <span className="text-primary">{icon}</span>
        {title}
        <svg
          className="chev ml-auto size-4 text-muted-foreground transition-transform"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  )
}

function FactorPanel({
  title,
  tone,
  icon,
  items,
}: {
  title: string
  tone: "up" | "down"
  icon: React.ReactNode
  items: string[]
}) {
  const toneClass = tone === "up" ? "text-up" : "text-down"
  return (
    <details
      open
      className="group rounded-xl border border-border bg-card p-4 sm:p-5 [&[open]>summary_.chev]:rotate-180"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium [&::-webkit-details-marker]:hidden">
        <span className={toneClass}>{icon}</span>
        {title}
        <svg
          className="chev ml-auto size-4 text-muted-foreground transition-transform"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <ul className="mt-3 space-y-2.5">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
            <span className={`mt-0.5 shrink-0 ${toneClass}`}>
              {tone === "up" ? (
                <Check className="size-4" />
              ) : (
                <X className="size-4" />
              )}
            </span>
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
