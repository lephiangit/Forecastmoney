"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import type { Asset, PricePoint, Candle, Kpis, Research } from "@/lib/forecast-data"
import { forecastApi, type CombinedForecastResponse } from "@/lib/api"
import { ForecastHeader } from "./forecast-header"
import { HorizonSlider } from "./horizon-slider"
import { KpiCards } from "./kpi-cards"
import { PriceForecastChart } from "./price-forecast-chart"
import { CandlestickChart } from "./candlestick-chart"
import { AiResearch } from "./ai-research"
import { RecommendationCard } from "./recommendation-card"

function seededRandom(str: string) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = Math.imul(31, hash) + str.charCodeAt(i) | 0;
  }
  return Math.abs(hash) / 2147483648; // 0 to 1
}

function mapApiResponse(res: CombinedForecastResponse, ticker: string): { asset: Asset; series: { points: PricePoint[]; candles: Candle[]; forecastStartDate: string; }; kpis: Kpis; research: Research } {
  const price = res.live?.price || res.current_price || 0;
  
  const asset: Asset = {
    ticker: res.live?.ticker || ticker,
    name: res.live?.name || res.ticker,
    kind: res.live?.type === "CRYPTOCURRENCY" ? "crypto" : "equity",
    price: price,
    change24h: res.live?.change_pct || 0,
    marketCap: "N/A",
    volume: res.live?.volume ? `$${(res.live.volume / 1e9).toFixed(2)}B` : "N/A",
  };

  const points: PricePoint[] = [];
  const candles: Candle[] = [];

  // 1. Historical Data
  let lastHistClose = price;
  let lastHistDate = new Date().toISOString().substring(0,10);
  if (res.historical && res.historical.length > 0) {
    res.historical.forEach(bar => {
      const d = bar.date.substring(0, 10);
      points.push({
        date: d,
        historical: bar.close,
        forecast: null,
        sentiment: null,
        upper: null,
        lower: null,
      });
      candles.push({
        date: d,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        forecast: false,
      });
    });
    lastHistClose = res.historical[res.historical.length - 1].close;
    lastHistDate = res.historical[res.historical.length - 1].date.substring(0, 10);
  } else {
    points.push({
      date: lastHistDate,
      historical: price,
      forecast: null,
      sentiment: null,
      upper: null,
      lower: null,
    });
  }

  const lastHistIndex = points.length - 1;
  points[lastHistIndex].forecast = points[lastHistIndex].historical;
  points[lastHistIndex].sentiment = points[lastHistIndex].historical;
  points[lastHistIndex].upper = points[lastHistIndex].historical;
  points[lastHistIndex].lower = points[lastHistIndex].historical;

  const forecastStartDate = points[lastHistIndex].date;

  // 2. Forecast Data
  const medianFC = res.tft.median || [];
  const lowerFC = res.tft.lower_q10 || [];
  const upperFC = res.tft.upper_q90 || [];
  const sentFC = res.sentiment_fusion?.median || [];

  let prevClose = lastHistClose;
  const dailyVol = (asset.kind === "crypto" ? 0.028 : 0.016) * price;

  for (let i = 0; i < medianFC.length; i++) {
    const d = medianFC[i].date.substring(0, 10);
    const fc = medianFC[i].price;
    const sent = sentFC[i]?.price || null;
    const lower = lowerFC[i]?.price || null;
    const upper = upperFC[i]?.price || null;

    points.push({
      date: d,
      historical: null,
      forecast: fc,
      sentiment: sent,
      upper: upper,
      lower: lower,
    });

    const open = prevClose;
    const wick = dailyVol * 0.6;
    const rand1 = seededRandom(d + "high");
    const rand2 = seededRandom(d + "low");
    const high = Math.max(open, fc) + rand1 * wick;
    const low = Math.min(open, fc) - rand2 * wick;

    candles.push({
      date: d,
      open: open,
      high: high,
      low: low,
      close: fc,
      forecast: true,
    });
    prevClose = fc;
  }

  const finalTarget = medianFC.length > 0 ? medianFC[medianFC.length - 1].price : price;
  const expectedReturn = price > 0 ? ((finalTarget - price) / price) * 100 : 0;
  
  const finalUpper = upperFC.length > 0 ? upperFC[upperFC.length - 1].price : price;
  const finalLower = lowerFC.length > 0 ? lowerFC[lowerFC.length - 1].price : price;
  const volatility = finalTarget > 0 ? (finalUpper - finalLower) / finalTarget : 0;
  const riskLevel = volatility > 0.28 ? "High" : volatility > 0.14 ? "Medium" : "Low";

  // Re-map research from API format
  let bullishFactors: string[] = [];
  let bearishFactors: string[] = [];
  if (res.research?.key_factors) {
    bullishFactors = res.research.key_factors.filter(f => !f.toLowerCase().includes("risk") && !f.toLowerCase().includes("bear"));
    bearishFactors = res.research.key_factors.filter(f => f.toLowerCase().includes("risk") || f.toLowerCase().includes("bear"));
  }

  let rec = (res.research?.recommendation || "HOLD").toUpperCase();
  if (rec !== "BUY" && rec !== "SELL" && rec !== "HOLD") rec = "HOLD";

  const kpis: Kpis = {
    expectedReturn: Math.round(expectedReturn * 100) / 100,
    targetPrice: finalTarget,
    confidence: Math.round((res.research?.confidence || 0.75) * 100),
    riskLevel,
  };

  const research: Research = {
    summary: res.research?.summary || "Đang phân tích dữ liệu...",
    bullish: bullishFactors.length ? bullishFactors : ["Đang tổng hợp thông tin..."],
    bearish: bearishFactors.length ? bearishFactors : ["Không có thông tin tiêu cực đáng kể."],
    newsSentiment: {
      label: res.research?.sentiment || "NEUTRAL",
      score: Math.round((res.research?.sentiment_score || 0) * 100),
      sources: res.research?.headlines?.length || 0,
    },
    recommendation: rec as "BUY" | "HOLD" | "SELL",
    timeHorizon: `${res.days} days`,
    generatedAt: res.generated_at,
  };

  return { asset, series: { points, candles, forecastStartDate }, kpis, research };
}

export function ForecastDetail({ ticker }: { ticker: string }) {
  const [horizon, setHorizon] = useState(14)
  const [showSentiment, setShowSentiment] = useState(true)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [mappedData, setMappedData] = useState<{ asset: Asset; series: { points: PricePoint[]; candles: Candle[]; forecastStartDate: string; }; kpis: Kpis; research: Research } | null>(null)

  useEffect(() => {
    let active = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const res = await forecastApi.combined(ticker, horizon);
        if (!active) return;
        setMappedData(mapApiResponse(res, ticker));
      } catch (err: unknown) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Không thể tải dữ liệu dự báo. Vui lòng thử lại sau.");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadData();
    return () => { active = false };
  }, [ticker, horizon])

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="bg-[#1e2329] border border-[#f6465d] p-6 rounded-xl text-[#f6465d] text-center font-medium">
          Lỗi: {error}
        </div>
      </div>
    )
  }

  if (loading || !mappedData) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 space-y-4 fade-in">
        <div className="flex items-center gap-3 text-[#f0b90b] mb-4">
          <Loader2 className="animate-spin size-5" />
          <span className="font-medium">Đang chạy mô hình AI TFT + Sentiment...</span>
        </div>
        <div className="shimmer h-[72px] rounded-xl" />
        <div className="shimmer h-[56px] rounded-xl" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="shimmer h-[100px] rounded-xl" />
          <div className="shimmer h-[100px] rounded-xl" />
          <div className="shimmer h-[100px] rounded-xl" />
          <div className="shimmer h-[100px] rounded-xl" />
        </div>
        <div className="shimmer h-[400px] rounded-xl" />
        <div className="shimmer h-[300px] rounded-xl" />
      </div>
    )
  }

  const { asset, series, kpis, research } = mappedData;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 fade-in">
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
