"use client"

import { useMemo, useState } from "react"
import type { Asset } from "@/lib/forecast-data"
import {
  buildKpis,
  buildResearch,
  buildSeries,
} from "@/lib/forecast-data"
import { ForecastHeader } from "./forecast-header"
import { HorizonSlider } from "./horizon-slider"
import { KpiCards } from "./kpi-cards"
import { PriceForecastChart } from "./price-forecast-chart"
import { CandlestickChart } from "./candlestick-chart"
import { AiResearch } from "./ai-research"
import { RecommendationCard } from "./recommendation-card"

export function ForecastDetail({ asset }: { asset: Asset }) {
  const [horizon, setHorizon] = useState(14)
  const [showSentiment, setShowSentiment] = useState(true)

  // Recomputed whenever the horizon changes — stands in for re-calling the
  // forecast API with a new horizon parameter.
  const { series, kpis, research } = useMemo(() => {
    const series = buildSeries(asset, horizon)
    const kpis = buildKpis(asset, series)
    const research = buildResearch(asset, kpis, horizon)
    return { series, kpis, research }
  }, [asset, horizon])

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="space-y-4">
        <ForecastHeader asset={asset} />

        <HorizonSlider value={horizon} onChange={setHorizon} />

        <KpiCards asset={asset} kpis={kpis} />

        <PriceForecastChart
          asset={asset}
          points={series.points}
          forecastStartDate={series.forecastStartDate}
          showSentiment={showSentiment}
          onToggleSentiment={setShowSentiment}
        />

        <CandlestickChart
          asset={asset}
          candles={series.candles}
          forecastStartDate={series.forecastStartDate}
        />

        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <AiResearch asset={asset} research={research} />
          <RecommendationCard asset={asset} kpis={kpis} research={research} />
        </div>
      </div>
    </div>
  )
}
