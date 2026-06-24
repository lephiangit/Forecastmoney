import Link from "next/link"
import { ArrowLeft, TrendingDown, TrendingUp } from "lucide-react"
import type { Asset } from "@/lib/forecast-data"
import { formatPrice } from "@/lib/forecast-data"
import { cn } from "@/lib/utils"

export function ForecastHeader({ asset }: { asset: Asset }) {
  const up = asset.change24h >= 0

  return (
    <header className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <Link
        href="/"
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        All assets
      </Link>

      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-sm font-bold text-primary-foreground">
            {asset.ticker.slice(0, 3)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                {asset.ticker}
              </h1>
              <span className="rounded-md bg-secondary px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {asset.kind}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{asset.name}</p>
          </div>
        </div>

        <div className="sm:text-right">
          <div className="flex items-baseline gap-3 sm:justify-end">
            <span className="font-mono text-3xl font-semibold tabular-nums">
              {formatPrice(asset.price, asset)}
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-semibold tabular-nums",
                up
                  ? "bg-up/15 text-up"
                  : "bg-down/15 text-down",
              )}
            >
              {up ? (
                <TrendingUp className="size-4" />
              ) : (
                <TrendingDown className="size-4" />
              )}
              {up ? "+" : ""}
              {asset.change24h.toFixed(2)}%
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            24H change
          </p>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4 sm:grid-cols-4">
        <Stat label="Market Cap" value={asset.marketCap} />
        <Stat label="24H Volume" value={asset.volume} />
        <Stat label="Asset Type" value={asset.kind === "crypto" ? "Cryptocurrency" : "Equity"} />
        <Stat label="Symbol" value={asset.ticker} />
      </dl>
    </header>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-mono text-sm font-medium tabular-nums">
        {value}
      </dd>
    </div>
  )
}
