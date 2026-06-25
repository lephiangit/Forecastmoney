import {
  MARKET_ASSETS,
  buildForecast,
  SIGNALS,
  RESEARCH,
  buildPortfolio,
  TRANSACTIONS,
  AUTO_TRADE_CONFIG,
  AUTO_TRADE_STATS,
  ADMIN_USERS,
  MODEL_ACCURACY,
  SYSTEM_METRICS,
  RESEARCH_QUEUE,
} from "./data"
import type {
  MarketAsset,
  Forecast,
  Signal,
  ResearchReport,
  Portfolio,
  Transaction,
  AutoTradeConfig,
  AutoTradeStats,
  AdminUser,
  ModelAccuracy,
  SystemMetric,
  ResearchQueueItem,
} from "./types"

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL

// Jitter live-ish values so the UI feels real even with local data.
function jitter<T extends { price: number; change: number; changePercent: number }>(
  asset: T,
): T {
  const factor = 1 + (Math.random() - 0.5) * 0.004
  const price = Number((asset.price * factor).toFixed(2))
  const change = Number((asset.change + (Math.random() - 0.5) * asset.price * 0.001).toFixed(2))
  return {
    ...asset,
    price,
    change,
    changePercent: Number(((change / (price - change)) * 100).toFixed(2)),
  }
}

async function tryFetch<T>(path: string): Promise<T | null> {
  if (!BASE_URL) return null
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as T
  } catch {
    return null
  }
}

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms))

export const api = {
  async getMarkets(): Promise<MarketAsset[]> {
    const real = await tryFetch<MarketAsset[]>("/api/markets")
    if (real) return real
    await delay()
    return MARKET_ASSETS.map(jitter)
  },

  async getAsset(ticker: string): Promise<MarketAsset | undefined> {
    const real = await tryFetch<MarketAsset>(`/api/markets/${ticker}`)
    if (real) return real
    await delay()
    const a = MARKET_ASSETS.find((m) => m.ticker === ticker.toUpperCase())
    return a ? jitter(a) : undefined
  },

  async getForecasts(): Promise<Forecast[]> {
    const real = await tryFetch<Forecast[]>("/api/forecasts")
    if (real) return real
    await delay()
    return MARKET_ASSETS.map((a) => buildForecast(a.ticker))
  },

  async getForecast(ticker: string): Promise<Forecast> {
    const real = await tryFetch<Forecast>(`/api/forecasts/${ticker}`)
    if (real) return real
    await delay()
    return buildForecast(ticker.toUpperCase())
  },

  async getSignals(): Promise<Signal[]> {
    const real = await tryFetch<Signal[]>("/api/signals")
    if (real) return real
    await delay()
    return SIGNALS
  },

  async getResearch(): Promise<ResearchReport[]> {
    const real = await tryFetch<ResearchReport[]>("/api/research")
    if (real) return real
    await delay()
    return RESEARCH
  },

  async getResearchReport(ticker: string): Promise<ResearchReport | undefined> {
    const real = await tryFetch<ResearchReport>(`/api/research/${ticker}`)
    if (real) return real
    await delay()
    return RESEARCH.find((r) => r.ticker === ticker.toUpperCase())
  },

  async translateReport(id: string): Promise<{ content_vi: string; translated_at: string }> {
    const real = await tryFetch<{ content_vi: string; translated_at: string }>(
      `/api/research/${id}/translate`,
    )
    if (real) return real
    await delay(600)
    const report = RESEARCH.find((r) => r.id === id)
    return {
      content_vi:
        report?.content_vi ??
        "## Bản dịch tự động\n\nNội dung báo cáo đã được dịch sang tiếng Việt bởi Gemini AI. " +
          (report?.summary ?? ""),
      translated_at: new Date().toISOString(),
    }
  },

  async getPortfolio(): Promise<Portfolio> {
    const real = await tryFetch<Portfolio>("/api/portfolio")
    if (real) return real
    await delay()
    return buildPortfolio()
  },

  async getTransactions(): Promise<Transaction[]> {
    const real = await tryFetch<Transaction[]>("/api/transactions")
    if (real) return real
    await delay()
    return TRANSACTIONS
  },

  async getAutoTradeConfig(): Promise<AutoTradeConfig> {
    const real = await tryFetch<AutoTradeConfig>("/api/auto-trade/config")
    if (real) return real
    await delay()
    return AUTO_TRADE_CONFIG
  },

  async getAutoTradeStats(): Promise<AutoTradeStats> {
    const real = await tryFetch<AutoTradeStats>("/api/auto-trade/stats")
    if (real) return real
    await delay()
    return AUTO_TRADE_STATS
  },

  async getAdminUsers(): Promise<AdminUser[]> {
    const real = await tryFetch<AdminUser[]>("/api/admin/users")
    if (real) return real
    await delay()
    return ADMIN_USERS
  },

  async getModelAccuracy(): Promise<ModelAccuracy[]> {
    const real = await tryFetch<ModelAccuracy[]>("/api/admin/accuracy")
    if (real) return real
    await delay()
    return MODEL_ACCURACY
  },

  async getSystemMetrics(): Promise<SystemMetric[]> {
    const real = await tryFetch<SystemMetric[]>("/api/admin/system")
    if (real) return real
    await delay()
    return SYSTEM_METRICS
  },

  async getResearchQueue(): Promise<ResearchQueueItem[]> {
    const real = await tryFetch<ResearchQueueItem[]>("/api/admin/research-queue")
    if (real) return real
    await delay()
    return RESEARCH_QUEUE
  },
}
