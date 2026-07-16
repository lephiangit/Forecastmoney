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
      cache: "no-store",
      ...options,
      headers,
    })
    if (res.status === 401 && typeof window !== "undefined") {
      const hadToken = !!localStorage.getItem("forecast_ai_token")
      // Token missing or expired – clear stale auth state
      const { useAuthStore } = require("./store")
      useAuthStore.getState().logout()

      // Only redirect if we're not already on login/register/callback pages AND they actually had a token
      const p = window.location.pathname
      if (hadToken && !p.startsWith("/login") && !p.startsWith("/register") && !p.startsWith("/auth/")) {
        window.location.href = "/login?reason=session_expired"
      }
      throw new Error("Unauthorized")
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as T
  } catch {
    return null
  }
}

const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms))

export const api = {
  async getMarkets(): Promise<MarketAsset[]> {
    let watchlistTickers: string[] = []
    try {
      const watchlist = await api.getWatchlist()
      if (watchlist && watchlist.length > 0) {
        watchlistTickers = [...watchlist]
      }
    } catch {
      // Ignore if not logged in
    }

    const defaultTickers = [
      "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD",
      "DOGE-USD", "AVAX-USD", "AAPL", "NVDA", "TSLA", "FPT.VN", "HPG.VN", "VCB.VN"
    ]

    const allTickers = Array.from(new Set([...defaultTickers, ...watchlistTickers])).slice(0, 30)
    const res = await tryFetch<{ data: any[] }>(`/market/overview?tickers=${allTickers.join(",")}`)
    if (res?.data) {
      return res.data.map((d: any) => ({
        ...d,
        changePercent: d.change_pct ?? d.changePercent ?? 0,
        high24h: d.high_24h ?? d.high24h ?? d.price ?? 0,
        low24h: d.low_24h ?? d.low24h ?? d.price ?? 0,
        category: d.category ?? d.type ?? "stock",
        sparkline: d.sparkline || [],
      }))
    }
    return MARKET_ASSETS
  },

  async getAsset(ticker: string): Promise<MarketAsset | undefined> {
    const res = await tryFetch<MarketAsset>(`/market/live/${ticker}`)
    return res || undefined
  },

  async searchTickers(query: string): Promise<{ symbol: string; name: string; exchange: string; type: string }[]> {
    const res = await tryFetch<{ results: any[] }>(`/market/search?q=${encodeURIComponent(query)}`)
    return res?.results || []
  },

  async getForecasts(): Promise<Forecast[]> {
    const defaultTickers = ["BTC-USD", "ETH-USD", "NVDA", "AAPL", "TSLA"]
    let tickers: string[] = [...defaultTickers]
    
    try {
      const watchlist = await api.getWatchlist()
      if (watchlist && watchlist.length > 0) {
        for (const t of watchlist) {
          if (!tickers.includes(t)) {
            tickers.push(t)
          }
        }
      }
    } catch {
      // Ignore watchlist errors
    }
    
    // Limit to 12 tickers max to prevent overloading
    tickers = tickers.slice(0, 12)
    
    return Promise.all(tickers.map(async (ticker) => {
      const f = await api.getForecast(ticker)
      return f
    }))
  },

  async getForecast(ticker: string): Promise<Forecast> {
    try {
      const real = await tryFetch<any>(`/forecast/combined/${ticker}`)
      
      const forecastData = real?.sentiment_fusion?.available ? real.sentiment_fusion : real?.tft
      
      if (real && forecastData && forecastData.median && forecastData.median.length > 0) {
        const currentPrice = real.current_price || 0
        const predicted = forecastData.median.map((m: any) => ({ time: m.date, value: Number(m.price) || 0 }))
        const upperBand = (forecastData.upper_q90 || []).map((m: any) => ({ time: m.date, value: Number(m.price) || 0 }))
        const lowerBand = (forecastData.lower_q10 || []).map((m: any) => ({ time: m.date, value: Number(m.price) || 0 }))
        
        const targetPrice = predicted[predicted.length - 1].value
        const expectedReturn = currentPrice > 0 ? ((targetPrice - currentPrice) / currentPrice) * 100 : 0
        const direction = expectedReturn > 1 ? "up" : expectedReturn < -1 ? "down" : "neutral"
        
        const baseTicker = ticker.split("-")[0]
        const fallback = buildForecast(baseTicker) || buildForecast(ticker)

        return {
          ticker: real.ticker || ticker,
          name: fallback?.name || ticker,
          currentPrice,
          targetPrice,
          horizonDays: real.days || 30,
          confidence: real?.research?.confidence
            ? (real.research.confidence <= 1 ? Math.round(real.research.confidence * 100) : real.research.confidence)
            : (70 + Math.floor(Math.random() * 20)),
          direction,
          expectedReturn,
          model: real.model || "TFT",
          history: real.historical?.length > 0 
            ? real.historical.map((h: any) => ({ time: h.date, value: h.close }))
            : fallback?.history || [],
          predicted,
          upperBand,
          lowerBand,
          updatedAt: real.generated_at || new Date().toISOString()
        }
      }
    } catch (e) {
      console.error("Forecast fetch failed, using fallback:", e)
    }

    const baseTicker = ticker.split("-")[0]
    const fallback = buildForecast(baseTicker) || buildForecast(ticker)
    if (fallback) return fallback
    
    // Return a safe minimal fallback so Promise.all in getForecasts never rejects
    return {
      ticker,
      name: ticker,
      currentPrice: 0,
      targetPrice: 0,
      horizonDays: 30,
      confidence: 0,
      direction: "neutral" as const,
      expectedReturn: 0,
      model: "N/A",
      history: [],
      predicted: [],
      upperBand: [],
      lowerBand: [],
      updatedAt: new Date().toISOString(),
    }
  },

  async getLeaderboard(): Promise<LeaderboardEntry[]> {
    const real = await tryFetch<LeaderboardEntry[]>("/admin/leaderboard")
    return real || []
  },

  async getResearch(): Promise<ResearchReport[]> {
    const real = await tryFetch<any>("/research/reports")
    return Array.isArray(real) ? real : RESEARCH
  },

  async getResearchReport(ticker: string): Promise<ResearchReport | undefined> {
    const real = await tryFetch<ResearchReport>(`/research/${ticker}`)
    return real || RESEARCH.find((r) => r.ticker === ticker.toUpperCase())
  },

  async getResearchHistory(params: { limit?: number; offset?: number; ticker?: string; sentiment?: string } = {}): Promise<{ items: ResearchReport[]; count: number }> {
    const searchParams = new URLSearchParams()
    if (params.limit) searchParams.set("limit", params.limit.toString())
    if (params.offset) searchParams.set("offset", params.offset.toString())
    if (params.ticker) searchParams.set("ticker", params.ticker)
    if (params.sentiment) searchParams.set("sentiment", params.sentiment)
    
    const real = await tryFetch<any>(`/research/archive?${searchParams.toString()}`)
    if (real && real.items) {
      return { items: real.items, count: real.count }
    }
    return { items: [], count: 0 }
  },

  async translateReport(id: string): Promise<{ content_vi: string; translated_at: string }> {
    const real = await tryFetch<{ content_vi: string; translated_at: string }>(
      `/research/${id}/translate`,
      { method: "POST" },
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

  async getPortfolioHistory(days: number = 90): Promise<any[]> {
    const res = await tryFetch<{ history: any[] }>(`/admin/portfolio/history?days=${days}`)
    return res?.history || []
  },

  async getPortfolio(): Promise<Portfolio> {
    const real = await tryFetch<any>("/admin/portfolio")
    if (real) {
      // Get history alongside portfolio
      // We use the chart endpoint to get the trade-by-trade chart which is better than daily snapshots
      const historyRes = await tryFetch<any>("/admin/portfolio/chart")
      let history: any[] = []
      
      if (historyRes && Array.isArray(historyRes)) {
        history = historyRes.map((h: any) => ({
          time: h.time,
          value: Number(h.balance) || 0
        }))
      }

      // If no history exists, use a flat line based on current balance
      if (history.length === 0) {
        history = [
          { time: new Date(Date.now() - 86400000).toISOString(), value: real.current_balance || 0 },
          { time: new Date().toISOString(), value: real.current_balance || 0 }
        ]
      }

      const holdings = Object.entries(real.positions || {}).map(([k, v]: any) => {
        const qty = Number(v.qty) || 0
        const costBasis = Number(v.total_cost) || 0
        const avgPrice = Number(v.avg_cost) || 0
        const currentPrice = avgPrice // Fallback, could be updated with real live quotes if available
        const marketValue = qty * currentPrice
        
        return {
          ticker: k,
          name: k,
          quantity: qty,
          avgPrice: avgPrice,
          currentPrice: currentPrice,
          marketValue: marketValue,
          costBasis: costBasis,
          unrealizedPnl: marketValue - costBasis,
          unrealizedPnlPercent: costBasis > 0 ? ((marketValue - costBasis) / costBasis) * 100 : 0,
          allocation: 0 // Will compute below
        }
      })

      const investedValue = holdings.reduce((sum, h) => sum + h.marketValue, 0)
      
      if (investedValue > 0) {
        holdings.forEach(h => {
          h.allocation = (h.marketValue / investedValue) * 100
        })
      }

      // mapping backend shape to frontend Portfolio
      return {
        cash: real.current_balance,
        totalValue: (real.current_balance || 0) + investedValue,
        investedValue: investedValue,
        totalPnl: real.total_pnl,
        totalPnlPercent: real.initial_balance > 0 ? (real.total_pnl / real.initial_balance) * 100 : 0,
        dayPnl: 0,
        dayPnlPercent: 0,
        holdings: holdings,
        history: history
      }
    }
    return buildPortfolio()
  },

  async getTransactions(): Promise<Transaction[]> {
    const real = await tryFetch<any>("/admin/portfolio")
    if (real && real.recent_trades) {
      return real.recent_trades.map((t: any) => ({
        id: t.id?.toString() || Math.random().toString(),
        ticker: t.ticker,
        action: t.action,
        quantity: t.quantity,
        price: t.price,
        total: t.total_value,
        source: t.model_signal === "AUTO" ? "auto" : "manual",
        createdAt: t.trade_time
      }))
    }
    return TRANSACTIONS
  },

  async getBotConfig(): Promise<{ amount: number; end_time: string | null }> {
    const real = await tryFetch<any>("/admin/trading/config")
    return real || { amount: 500, end_time: null }
  },

  async startBot(amount: number, durationHours: number, assets: string[]) {
    return tryFetch("/admin/trading/start", {
      method: "POST",
      body: JSON.stringify({ amount, duration_hours: durationHours, assets })
    })
  },

  async stopBot() {
    return tryFetch("/admin/trading/stop", { method: "POST" })
  },

  async getAutoTradeStats(): Promise<AutoTradeStats> {
    try {
      const real = await tryFetch<any>("/admin/portfolio")
      if (real) {
        const activePositions = real.positions ? Object.keys(real.positions).length : 0
        const initial = real.initial_balance || 10000
        const current = real.current_balance || 10000
        const botPnl = current - initial
        const botPnlPercent = initial > 0 ? (botPnl / initial) * 100 : 0
        
        let totalTrades = (real.win_trades || 0) + (real.loss_trades || 0)
        if (real.recent_trades) {
           const autoTrades = real.recent_trades.filter((t: any) => t.model_signal === "AUTO").length
           if (autoTrades > totalTrades) totalTrades = autoTrades
        }

        return {
          winRate: real.win_rate || 0,
          totalTrades,
          activePositions,
          pnl: botPnl,
          totalReturn: botPnlPercent,
        }
      }
    } catch(e) {}
    return { winRate: 0, totalTrades: 0, activePositions: 0, pnl: 0, totalReturn: 0 }
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
    const real = await tryFetch<SystemMetric[]>("/admin/system")
    if (real) return real
    await delay()
    return SYSTEM_METRICS
  },

  async getResearchQueue(): Promise<ResearchQueueItem[]> {
    const real = await tryFetch<ResearchQueueItem[]>("/admin/research-queue")
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

  async updateProfile(name: string): Promise<boolean> {
    const res = await tryFetch<{success: boolean}>("/auth/profile", {
      method: "PUT",
      body: JSON.stringify({ name })
    })
    return res?.success || false
  },

  async login(username: string, password: string) {
    if (!BASE_URL) throw new Error("API URL not configured")
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
    if (!BASE_URL) throw new Error("API URL not configured")
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
  },

  async loginWithGoogle(accessToken: string) {
    if (!BASE_URL) throw new Error("API URL not configured")
    const res = await fetch(`${BASE_URL}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Google login failed");
    }
    return res.json()
  },

  async getNotifications(): Promise<import("./types").Notification[]> {
    const res = await tryFetch<{ success: boolean; notifications: import("./types").Notification[] }>("/notifications")
    return res?.notifications || []
  },

  async markNotificationRead(id: number): Promise<boolean> {
    const res = await tryFetch<{ success: boolean }>(`/notifications/${id}/read`, { method: "POST" })
    return res?.success || false
  },

  async createNotification(title: string, message: string, user_id: number | null = null): Promise<boolean> {
    const res = await tryFetch<{ success: boolean }>("/admin/notifications", {
      method: "POST",
      body: JSON.stringify({ title, message, user_id })
    })
    return res?.success || false
  },

  async deleteNotification(id: number): Promise<boolean> {
    const res = await tryFetch<{ success: boolean }>(`/notifications/${id}`, { method: "DELETE" })
    return res?.success || false
  },

  async changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; message: string }> {
    const res = await tryFetch<{ success: boolean; message: string }>("/auth/change-password", {
      method: "PUT",
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
    })
    if (!res) throw new Error("Failed to change password. Please check your connection.")
    return res
  },

  async forgotPassword(email: string): Promise<{ success: boolean; message: string }> {
    if (!BASE_URL) throw new Error("API URL not configured")
    const res = await fetch(`${BASE_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Failed to request password reset");
    }
    return res.json()
  },

  async resetPassword(email: string, newPassword: string, supabaseToken: string): Promise<{ success: boolean; message: string }> {
    if (!BASE_URL) throw new Error("API URL not configured")
    const res = await fetch(`${BASE_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        email, 
        new_password: newPassword, 
        supabase_token: supabaseToken 
      })
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Failed to reset password");
    }
    return res.json()
  },

  async askCopilot(message: string, history: { role: "user" | "assistant"; content: string }[] = [], lang: "en" | "vi" = "vi"): Promise<{ reply: string; href?: string }> {
    if (!BASE_URL) return { reply: "API URL not configured" }
    try {
      const res = await fetch(`${BASE_URL}/chat/copilot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, lang })
      })
      if (!res.ok) {
        return { reply: lang === "vi" ? "Xin lỗi bạn, hiện tại tôi không thể kết nối tới server. Bạn thử lại sau nhé!" : "Sorry, I cannot connect to the server right now. Please try again later!" }
      }
      return await res.json()
    } catch (e) {
      return { reply: lang === "vi" ? "Lỗi kết nối rồi. Vui lòng kiểm tra lại mạng!" : "Connection error. Please check your network!" }
    }
  },

  // ── Backtesting ──────────────────────────────────────────────────────────

  async runBacktest(params: {
    ticker: string
    days_back: number
    strategy: string
    initial_balance: number
    trade_amount: number
  }): Promise<import("./types").BacktestResult | null> {
    return tryFetch<import("./types").BacktestResult>("/backtest/run", {
      method: "POST",
      body: JSON.stringify(params),
    })
  },

  // ── Technical Data ───────────────────────────────────────────────────────

  async getTickerWithIndicators(ticker: string, period: string = "1y"): Promise<import("./types").TickerDetail | null> {
    return tryFetch<import("./types").TickerDetail>(`/market/ticker/${ticker}?period=${period}&indicators=true`)
  },

  // ── Price Alerts ─────────────────────────────────────────────────────────

  async getPriceAlerts(): Promise<import("./types").PriceAlert[]> {
    const res = await tryFetch<{ alerts: import("./types").PriceAlert[] }>("/alerts")
    return res?.alerts || []
  },

  async createPriceAlert(ticker: string, condition: "above" | "below", targetPrice: number): Promise<boolean> {
    const res = await tryFetch<{ success: boolean }>("/alerts", {
      method: "POST",
      body: JSON.stringify({ ticker, condition, target_price: targetPrice }),
    })
    return res?.success || false
  },

  async deletePriceAlert(alertId: number): Promise<boolean> {
    const res = await tryFetch<{ success: boolean }>(`/alerts/${alertId}`, { method: "DELETE" })
    return res?.success || false
  },

  // ── Start Bot (extended) ─────────────────────────────────────────────────

  async startBotAdvanced(params: {
    amount: number
    duration_hours: number
    assets: string[]
    strategy: string
    stop_loss: number
    take_profit: number
    min_confidence: number
  }) {
    return tryFetch("/admin/trading/start", {
      method: "POST",
      body: JSON.stringify(params),
    })
  },
}


