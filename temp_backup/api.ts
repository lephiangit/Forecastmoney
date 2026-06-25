const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Timeout for Render free tier cold-start (can take 30-50s to wake up)
const API_TIMEOUT_MS = 60_000;
const MAX_RETRIES = 1;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  
  // Inject auth token if available in localStorage
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("forecast_ai_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        signal: controller.signal,
        headers: {
          ...headers,
          ...(options?.headers || {}),
        },
      });

      clearTimeout(timeout);

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));

        // Retry on 503 (backend waking up) or 502 (proxy error)
        if ((res.status === 503 || res.status === 502) && attempt < MAX_RETRIES) {
          lastError = new Error(err.detail || `API error ${res.status}`);
          await new Promise(r => setTimeout(r, 3000)); // Wait 3s before retry
          continue;
        }

        throw new Error(err.detail || `API error ${res.status}`);
      }

      return res.json();
    } catch (e: unknown) {
      clearTimeout(timeout);

      const err = e as Error;
      // Retry on network errors (backend cold-start)
      const isRetryable = err.name === "AbortError" || err.name === "TypeError" || err.message?.includes("fetch");
      if (isRetryable && attempt < MAX_RETRIES) {
        lastError = err;
        await new Promise(r => setTimeout(r, 3000));
        continue;
      }

      if (err.name === "AbortError") {
        throw new Error("Request timed out — backend may be starting up. Please try again.");
      }
      throw e;
    }
  }

  throw lastError || new Error("Request failed after retries");
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface LiveQuote {
  ticker: string;
  name?: string;
  price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  prev_close: number;
  change: number;
  change_pct: number;
  timestamp: string;
  type?: string;
}

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  rsi?: number;
  macd?: number;
  bb_upper?: number;
  bb_lower?: number;
  ma20?: number;
  ma50?: number;
}

export interface ForecastPoint {
  date: string;
  price: number;
}

export interface ForecastBand {
  median: ForecastPoint[] | null;
  lower_q10: ForecastPoint[] | null;
  upper_q90: ForecastPoint[] | null;
  available: boolean;
}

export interface ResearchContext {
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
  confidence: number;
  sentiment_score: number;
  summary: string;
  recommendation: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  key_factors: string[];
  headlines: { title: string; link: string; source: string }[];
  source: string;
  analyzed_at: string;
}

export interface CombinedForecastResponse {
  ticker: string;
  days: number;
  current_price: number | null;
  tft: ForecastBand;
  sentiment_fusion: ForecastBand;
  historical: OHLCVBar[] | null;
  research_used: boolean;
  research: ResearchContext;
  live: LiveQuote | null;
  generated_at: string;
}

export interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

// ── Market API ─────────────────────────────────────────────────────────────────

export const marketApi = {
  overview: (tickers?: string[]) => {
    const q = tickers ? `?tickers=${tickers.join(",")}` : "";
    return apiFetch<{ data: LiveQuote[]; count: number; fetched_at: string }>(`/market/overview${q}`);
  },
  search: (q: string) =>
    apiFetch<{ query: string; results: TickerSearchResult[]; count: number }>(`/market/search?q=${encodeURIComponent(q)}`),
  ticker: (id: string, period = "1y") =>
    apiFetch<{ ticker: string; name: string; period: string; live: LiveQuote | null; ohlcv: OHLCVBar[]; total_bars: number }>(`/market/ticker/${id}?period=${period}`),
  live: (id: string) =>
    apiFetch<LiveQuote>(`/market/live/${id}`),
  validate: (id: string) =>
    apiFetch<{ ticker: string; valid: boolean }>(`/market/validate/${id}`),
};

// ── Research API ───────────────────────────────────────────────────────────────

export interface ResearchAnalysis {
  ticker: string;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
  confidence: number;
  sentiment_score: number;
  summary: string;
  key_factors: string[];
  recommendation: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  price_target_bias?: string;
  source: string;
  analyzed_at: string;
  news_count: number;
  headlines: { title: string; link: string; source: string }[];
}

export const researchApi = {
  analyze: (ticker: string, force = false) =>
    apiFetch<ResearchAnalysis>(`/research/${ticker}?force=${force}`),
  news: (ticker: string) =>
    apiFetch<{ ticker: string; headlines: { title: string; link: string; source: string }[]; count: number; fetched_at: string }>(`/research/news/${ticker}`),
  history: (ticker: string, limit = 20) =>
    apiFetch<{ ticker: string; records: Record<string, unknown>[]; count: number }>(`/research/history/${ticker}?limit=${limit}`),
};

// ── Forecast API ───────────────────────────────────────────────────────────────

export const forecastApi = {
  combined: (ticker: string, days = 7) =>
    apiFetch<CombinedForecastResponse>(`/forecast/combined/${ticker}?days=${days}`),
  tft: (ticker: string, days = 7) =>
    apiFetch<{ forecast: ForecastBand; ticker: string; days: number }>(`/forecast/tft/${ticker}?days=${days}`),
};

// ── Auth API ───────────────────────────────────────────────────────────────────

export const authApi = {
  register: (username: string, password: string) =>
    apiFetch<{ token: string; username: string; message: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    apiFetch<{ token: string; username: string; message: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  getWatchlist: () =>
    apiFetch<{ success: boolean; watchlist: string[] }>("/auth/watchlist"),
  addWatchlist: (ticker: string) =>
    apiFetch<{ success: boolean; ticker: string }>("/auth/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),
  removeWatchlist: (ticker: string) =>
    apiFetch<{ success: boolean; ticker: string }>(`/auth/watchlist/${ticker}`, {
      method: "DELETE",
    }),
};

// ── Admin API ──────────────────────────────────────────────────────────────────

export interface Portfolio {
  initial_balance: number;
  current_balance: number;
  total_pnl: number;
  win_rate: number;
  win_trades: number;
  loss_trades: number;
  is_running: boolean;
  positions: Record<string, { qty: number; avg_cost: number }>;
  recent_trades: { trade_time: string, ticker: string, action: string, quantity: number, price: number, total_value: number, model_signal: string }[];
}

export const adminApi = {
  portfolio: () =>
    apiFetch<Portfolio>("/admin/portfolio"),
  trade: (ticker: string, action: "BUY" | "SELL", quantity: number) =>
    apiFetch("/admin/trade", {
      method: "POST",
      body: JSON.stringify({ ticker, action, quantity }),
    }),
  startTrading: async (budget: number) => apiFetch('/admin/trading/start', { method: 'POST', body: JSON.stringify({ budget }) }),
  stopTrading: async () => apiFetch('/admin/trading/stop', { method: 'POST' }),
  systemAccuracy: async () => apiFetch('/admin/system/accuracy', { method: 'GET' }),
  portfolioChart: () => apiFetch<{ time: string; balance: number; pnl: number }[]>("/admin/portfolio/chart"),
};
