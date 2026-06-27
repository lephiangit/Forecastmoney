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
  LeaderboardEntry,
} from "./types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL

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

async function tryFetch<T>(path: string, options?: RequestInit): Promise<T | null> {
  if (!BASE_URL) return null
  try {
    const headers: any = { "Content-Type": "application/json", ...options?.headers }
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("forecast_ai_token")
      if (token) headers["Authorization"] = `Bearer ${token}`
    }
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
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
    const res = await tryFetch<{ data: any[] }>("/market/overview")
    if (res?.data) {
      return res.data.map((d: any) => ({
        ...d,
        changePercent: d.change_pct ?? d.changePercent,
        high24h: d.high_24h ?? d.high24h,
        low24h: d.low_24h ?? d.low24h,
        sparkline: d.sparkline || [],
      }))
    }
    return MARKET_ASSETS.map(jitter)
  },

  async getAsset(ticker: string): Promise<MarketAsset | undefined> {
    const res = await tryFetch<MarketAsset>(`/market/live/${ticker}`)
    if (res) return res
    return MARKET_ASSETS.find((m) => m.ticker === ticker.toUpperCase())
  },

  async getForecasts(): Promise<Forecast[]> {
    return Promise.all(MARKET_ASSETS.slice(0, 5).map(async (a) => {
      const f = await api.getForecast(a.ticker)
      return f
    }))
  },

  async getForecast(ticker: string): Promise<Forecast> {
    const real = await tryFetch<Forecast>(`/forecast/${ticker}`)
    if (real) return real
    return buildForecast(ticker.toUpperCase())
  },

  async getLeaderboard(): Promise<LeaderboardEntry[]> {
    const real = await tryFetch<LeaderboardEntry[]>("/admin/leaderboard")
    return real || []
  },

  async getResearch(): Promise<ResearchReport[]> {
    const real = await tryFetch<ResearchReport[]>("/research/reports")
    return real || RESEARCH
  },

  async getResearchReport(ticker: string): Promise<ResearchReport | undefined> {
    const real = await tryFetch<ResearchReport>(`/research/reports?ticker=${ticker}`)
    return real || RESEARCH.find((r) => r.ticker === ticker.toUpperCase())
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
    const real = await tryFetch<any>("/admin/portfolio")
    if (real) {
      // mapping backend shape to frontend Portfolio
      return {
        cash: real.current_balance,
        totalValue: real.current_balance, // simplistic map
        investedValue: 0,
        totalPnl: real.total_pnl,
        totalPnlPercent: real.initial_balance > 0 ? (real.total_pnl / real.initial_balance) * 100 : 0,
        dayPnl: 0,
        dayPnlPercent: 0,
        holdings: Object.entries(real.positions).map(([k, v]: any) => ({
          ticker: k,
          name: k,
          quantity: v.qty,
          avgPrice: v.avg_cost,
          currentPrice: v.avg_cost,
          marketValue: v.total_cost,
          costBasis: v.total_cost,
          unrealizedPnl: 0,
          unrealizedPnlPercent: 0,
          allocation: 0
        })),
        history: []
      }
    }
    return buildPortfolio()
  },

  async getTransactions(): Promise<Transaction[]> {
    const real = await tryFetch<any>("/admin/portfolio")
    if (real && real.recent_trades) {
      return real.recent_trades.map((t: any) => ({
        id: t.id.toString(),
        ticker: t.ticker,
        action: t.action,
        quantity: t.quantity,
        price: t.price,
        total: t.total_value,
        source: "manual",
        createdAt: t.trade_time
      }))
    }
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
    const real = await tryFetch<AdminUser[]>("/admin/users")
    return real || ADMIN_USERS
  },

  async updateUserBalance(userId: string, amount: number) {
    return tryFetch(`/admin/users/${userId}/balance`, {
      method: "PUT",
      body: JSON.stringify({ amount })
    })
  },

  async updateUserStatus(userId: string) {
    return tryFetch(`/admin/users/${userId}/status`, { method: "PUT" })
  },

  async updateUserRole(userId: string) {
    return tryFetch(`/admin/users/${userId}/role`, { method: "PUT" })
  },

  async deleteUser(userId: string) {
    return tryFetch(`/admin/users/${userId}`, { method: "DELETE" })
  },

  async getModelAccuracy(): Promise<ModelAccuracy[]> {
    const real = await tryFetch<any>("/admin/system/accuracy")
    if (real && Array.isArray(real.records) && real.records.length > 0) {
      return real.records.map((r: any) => ({
        model: r.model_name || "TFT-v3",
        ticker: r.ticker || "UNKNOWN",
        accuracy: r.error_pct ? 1 - (r.error_pct / 100) : 0.85,
        mae: 0,
        rmse: 0,
        directionAccuracy: 0,
        predictions: 1,
        trend: []
      }))
    }
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

  async getWatchlist(): Promise<string[]> {
    const real = await tryFetch<string[]>("/admin/watchlist")
    if (real) return real
    return []
  },

  async addWatchlist(ticker: string): Promise<boolean> {
    const real = await tryFetch<{success: boolean}>(`/admin/watchlist?ticker=${ticker}`, { method: "POST" })
    return real?.success ?? false
  },

  async removeWatchlist(ticker: string): Promise<boolean> {
    const real = await tryFetch<{success: boolean}>(`/admin/watchlist/${ticker}`, { method: "DELETE" })
    return real?.success ?? false
  },

  async login(username: string, password: string) {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Invalid username or password");
    }
    return res.json()
  },

  async register(username: string, password: string) {
    const res = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Registration failed");
    }
    return res.json()
  }
}


