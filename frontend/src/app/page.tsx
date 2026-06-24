import Link from "next/link"
import { ArrowUpRight, Sparkles, TrendingDown, TrendingUp } from "lucide-react"
import { AVAILABLE_TICKERS, getAsset, formatPrice } from "@/lib/forecast-data"

export default function Page() {
  const assets = AVAILABLE_TICKERS.map((t) => getAsset(t)!).filter(Boolean)

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-16">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <Sparkles className="size-4" />
          AI Forecast Engine
        </div>
        <h1 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight text-balance sm:text-5xl">
          Price forecasts with confidence bands and automated research
        </h1>
        <p className="mt-4 max-w-xl text-pretty leading-relaxed text-muted-foreground">
          Pick an asset to view its AI-projected price path, forecast
          candlesticks, and a full research breakdown. Adjust the forecast
          horizon from 1 to 60 days.
        </p>

        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {assets.map((asset) => {
            const up = asset.change24h >= 0
            return (
              <Link
                key={asset.ticker}
                href={`/forecast/${asset.ticker}`}
                className="group rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-full bg-primary font-mono text-xs font-bold text-primary-foreground">
                      {asset.ticker.slice(0, 3)}
                    </div>
                    <div>
                      <p className="font-semibold">{asset.ticker}</p>
                      <p className="text-xs text-muted-foreground">
                        {asset.name}
                      </p>
                    </div>
                  </div>
                  <ArrowUpRight className="size-4 text-muted-foreground transition-colors group-hover:text-primary" />
                </div>

                <div className="mt-4 flex items-end justify-between">
                  <span className="font-mono text-lg font-semibold tabular-nums">
                    {formatPrice(asset.price, asset)}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 text-sm font-medium tabular-nums ${
                      up ? "text-up" : "text-down"
                    }`}
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
              </Link>
            )
          })}
        </div>
      </div>
    </main>
  )
}
