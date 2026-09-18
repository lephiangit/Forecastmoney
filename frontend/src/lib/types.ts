export type Trend = "up" | "down" | "neutral"

export interface MarketAsset {
  ticker: string
  name: string
  category: "crypto" | "index" | "commodity" | "stock"
  price: number
  change: number
  changePercent: number
  // `null` khi backend không trả biên độ ngày — KHÔNG lùi về `price`, vì như vậy
  // là bịa ra một biên độ bằng 0.
  high24h: number | null
  low24h: number | null
  volume: number
  marketCap?: number
  sparkline: number[]
}

export interface ForecastPoint {
  time: string
  value: number
}

export interface Forecast {
  ticker: string
  name: string
  currentPrice: number
  targetPrice: number
  horizonDays: number
  confidence: number
  direction: Trend
  expectedReturn: number
  model: string
  history: ForecastPoint[]
  predicted: ForecastPoint[]
  upperBand: ForecastPoint[]
  lowerBand: ForecastPoint[]
  updatedAt: string
}

export interface Signal {
  id: string
  ticker: string
  name: string
  action: "BUY" | "SELL" | "HOLD"
  confidence: number
  expectedReturn: number
  horizon: string
  reason: string
  createdAt: string
}

export interface ResearchReport {
  id: string
  ticker: string
  name: string
  title: string
  summary: string
  sentiment: "bullish" | "bearish" | "neutral"
  confidence: number
  author: string
  tags: string[] | string
  content_en: string
  content_vi?: string
  translated_at?: string
  createdAt: string
  readTime: number
  headlines?: { title: string; link: string; source: string }[]
}

export interface Holding {
  ticker: string
  name: string
  quantity: number
  avgPrice: number
  currentPrice: number
  marketValue: number
  costBasis: number
  unrealizedPnl: number
  unrealizedPnlPercent: number
  allocation: number
}

export interface Transaction {
  id: string
  ticker: string
  action: "BUY" | "SELL"
  quantity: number
  price: number
  total: number
  source: "manual" | "auto"
  createdAt: string
}

export interface Portfolio {
  cash: number
  totalValue: number
  investedValue: number
  totalPnl: number
  totalPnlPercent: number
  // null = backend chưa cung cấp số liệu lãi/lỗ trong ngày.
  // Trước đây hai trường này bị gán cứng 0 và vẫn hiển thị như số thật, nên thẻ
  // "Today P&L" luôn hiện $0.00 kèm huy hiệu xanh +0.00% — kể cả ngày bot lỗ nặng.
  dayPnl: number | null
  dayPnlPercent?: number
  holdings: Holding[]
  history: ForecastPoint[]
  is_running?: boolean
  started_at?: string | null
}

export interface AutoTradeConfig {
  enabled: boolean
  strategy: "conservative" | "balanced" | "aggressive"
  maxPositionSize: number
  minConfidence: number
  assets: string[]
  stopLoss: number
  takeProfit: number
}

export interface AutoTradeStats {
  totalTrades: number
  winRate: number
  totalReturn: number
  activePositions: number
  pnl: number
}

export interface AdminUser {
  id: string
  name: string
  email: string
  role: "user" | "admin"
  status: "active" | "suspended"
  portfolioValue: number
  joinedAt: string
  lastActive: string
}

export interface ModelAccuracy {
  model: string
  ticker: string
  // `null` = chưa đo được (không có bản ghi nào để tính), khác hẳn với giá trị 0.
  accuracy: number | null
  mae: number | null
  rmse: number | null
  directionAccuracy: number | null
  predictions: number
  trend: { time: string; value: number }[]
}

export interface SystemMetric {
  label: string
  value: number
  unit: string
  status: "healthy" | "warning" | "critical"
  /**
   * Dòng giải thích ngắn kèm theo chỉ số, do backend gửi xuống.
   * Ví dụ: "p95: 340 ms trên 1.204 request".
   * Tuỳ chọn, để các phản hồi cũ (không có trường này) vẫn dùng được.
   */
  hint?: string
}

export interface ResearchQueueItem {
  id: string
  ticker: string
  status: "pending" | "processing" | "completed" | "failed"
  requestedBy: string
  progress: number
  createdAt: string
}

export interface LeaderboardEntry {
  id: string
  username: string
  total_pnl: number
  win_trades: number
  loss_trades: number
  /** Thứ hạng do backend tính sẵn — tuỳ chọn để tương thích ngược. */
  rank?: number
  /** Tỷ lệ thắng tính trên số lệnh ĐÃ ĐÓNG, không phải tổng số giao dịch. */
  win_rate?: number
}

export interface Notification {
  id: number
  user_id: number | null
  title: string
  message: string
  is_read: boolean
  created_at: string
}

export interface PriceAlert {
  id: number
  user_id: number
  ticker: string
  condition: "above" | "below"
  target_price: number
  is_triggered: boolean
  created_at: string
  triggered_at: string | null
}

export interface BacktestTrade {
  date: string
  action: "BUY" | "SELL"
  price: number
  quantity: number
  total: number
  balance_after: number
  reason: string
}

export interface BacktestSummary {
  ticker: string
  strategy: string
  days_back: number
  initial_balance: number
  final_balance: number
  total_pnl: number
  total_pnl_pct: number
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  max_drawdown: number
  // Backend đổi tên từ `sharpe_ratio`: lãi suất phi rủi ro = 0 và tài khoản phần
  // lớn là tiền mặt, nên đây không phải tỷ lệ Sharpe theo đúng định nghĩa.
  return_to_volatility_ratio: number
  capital_deployed_pct?: number
  warnings?: string[]
}

export interface BacktestResult {
  summary: BacktestSummary
  trades: BacktestTrade[]
  equity_curve: { date: string; balance: number }[]
}

export interface TickerOHLCV {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  rsi?: number
  macd?: number
  macd_signal?: number
  bb_upper?: number
  bb_lower?: number
  ma20?: number
  ma50?: number
  atr?: number
}

export interface TickerDetail {
  ticker: string
  name: string
  period: string
  live: MarketAsset | null
  ohlcv: TickerOHLCV[]
  total_bars: number
}

