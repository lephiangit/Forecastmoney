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
  ForecastPoint,
} from "./types"

function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
}

function genSeries(
  base: number,
  points: number,
  volatility: number,
  drift: number,
  seed: number,
): ForecastPoint[] {
  const rand = seededRandom(seed)
  const out: ForecastPoint[] = []
  let value = base
  const now = Date.now()
  for (let i = points - 1; i >= 0; i--) {
    value = value * (1 + (rand() - 0.5) * volatility + drift)
    out.push({
      time: new Date(now - i * 86400000).toISOString().slice(0, 10),
      value: Number(value.toFixed(2)),
    })
  }
  return out
}

function sparkline(base: number, seed: number): number[] {
  const rand = seededRandom(seed)
  const out: number[] = []
  let v = base
  for (let i = 0; i < 24; i++) {
    v = v * (1 + (rand() - 0.5) * 0.03)
    out.push(Number(v.toFixed(2)))
  }
  return out
}

export const MARKET_ASSETS: MarketAsset[] = [
  {
    ticker: "FPT.VN",
    name: "FPT Corporation",
    category: "stock",
    price: 68000.0,
    change: 1200.0,
    changePercent: 1.80,
    high24h: 70400.0,
    low24h: 66800.0,
    volume: 15025959,
    marketCap: 74000000000000,
    sparkline: sparkline(68000, 120),
  },
  {
    ticker: "HPG.VN",
    name: "Hoa Phat Group",
    category: "stock",
    price: 22200.0,
    change: -200.0,
    changePercent: -0.89,
    high24h: 22400.0,
    low24h: 21800.0,
    volume: 23682685,
    marketCap: 130000000000000,
    sparkline: sparkline(22200, 120),
  },
  {
    ticker: "VCB.VN",
    name: "Vietcombank",
    category: "stock",
    price: 59400.0,
    change: 200.0,
    changePercent: 0.34,
    high24h: 59800.0,
    low24h: 58400.0,
    volume: 3363952,
    marketCap: 330000000000000,
    sparkline: sparkline(59400, 120),
  },
  {
    ticker: "BTC",
    name: "Bitcoin",
    category: "crypto",
    price: 67432.18,
    change: 1842.32,
    changePercent: 2.81,
    high24h: 68120.0,
    low24h: 65210.5,
    volume: 38_420_000_000,
    marketCap: 1_330_000_000_000,
    sparkline: sparkline(67432, 11),
  },
  {
    ticker: "ETH",
    name: "Ethereum",
    category: "crypto",
    price: 3521.44,
    change: -42.18,
    changePercent: -1.18,
    high24h: 3602.1,
    low24h: 3480.2,
    volume: 18_200_000_000,
    marketCap: 423_000_000_000,
    sparkline: sparkline(3521, 22),
  },
  {
    ticker: "SP500",
    name: "S&P 500",
    category: "index",
    price: 5478.32,
    change: 28.41,
    changePercent: 0.52,
    high24h: 5489.1,
    low24h: 5442.0,
    volume: 2_400_000_000,
    sparkline: sparkline(5478, 33),
  },
  {
    ticker: "NASDAQ",
    name: "Nasdaq 100",
    category: "index",
    price: 19842.11,
    change: 142.9,
    changePercent: 0.73,
    high24h: 19880.0,
    low24h: 19620.0,
    volume: 3_100_000_000,
    sparkline: sparkline(19842, 44),
  },
  {
    ticker: "DOW",
    name: "Dow Jones",
    category: "index",
    price: 38921.34,
    change: -88.21,
    changePercent: -0.23,
    high24h: 39010.0,
    low24h: 38840.0,
    volume: 1_200_000_000,
    sparkline: sparkline(38921, 55),
  },
  {
    ticker: "GOLD",
    name: "Gold",
    category: "commodity",
    price: 2342.6,
    change: 12.4,
    changePercent: 0.53,
    high24h: 2350.0,
    low24h: 2320.1,
    volume: 184_000_000,
    sparkline: sparkline(2342, 66),
  },
  {
    ticker: "OIL",
    name: "Crude Oil WTI",
    category: "commodity",
    price: 81.24,
    change: -1.32,
    changePercent: -1.6,
    high24h: 83.1,
    low24h: 80.9,
    volume: 92_000_000,
    sparkline: sparkline(81, 77),
  },
  {
    ticker: "AAPL",
    name: "Apple Inc.",
    category: "stock",
    price: 214.29,
    change: 3.12,
    changePercent: 1.48,
    high24h: 215.8,
    low24h: 210.4,
    volume: 54_000_000,
    marketCap: 3_290_000_000_000,
    sparkline: sparkline(214, 88),
  },
  {
    ticker: "NVDA",
    name: "NVIDIA Corp.",
    category: "stock",
    price: 126.57,
    change: 4.83,
    changePercent: 3.97,
    high24h: 128.0,
    low24h: 120.1,
    volume: 312_000_000,
    marketCap: 3_110_000_000_000,
    sparkline: sparkline(126, 99),
  },
  {
    ticker: "TSLA",
    name: "Tesla Inc.",
    category: "stock",
    price: 183.01,
    change: -2.44,
    changePercent: -1.32,
    high24h: 187.2,
    low24h: 181.0,
    volume: 98_000_000,
    marketCap: 583_000_000_000,
    sparkline: sparkline(183, 110),
  },
]

export function buildForecast(ticker: string): Forecast {
  const asset = MARKET_ASSETS.find((a) => a.ticker === ticker) ?? MARKET_ASSETS[0]
  const seed = ticker.split("").reduce((a, c) => a + c.charCodeAt(0), 0)
  const history = genSeries(asset.price * 0.92, 60, 0.04, 0.0015, seed)
  const last = history[history.length - 1].value
  const rand = seededRandom(seed + 7)
  const driftSign = rand() > 0.35 ? 1 : -1
  const predicted: ForecastPoint[] = []
  const upperBand: ForecastPoint[] = []
  const lowerBand: ForecastPoint[] = []
  let v = last
  const now = Date.now()
  for (let i = 1; i <= 30; i++) {
    v = v * (1 + driftSign * 0.004 + (rand() - 0.5) * 0.01)
    const time = new Date(now + i * 86400000).toISOString().slice(0, 10)
    const spread = v * (0.02 + i * 0.0015)
    predicted.push({ time, value: Number(v.toFixed(2)) })
    upperBand.push({ time, value: Number((v + spread).toFixed(2)) })
    lowerBand.push({ time, value: Number((v - spread).toFixed(2)) })
  }
  const target = predicted[predicted.length - 1].value
  const expectedReturn = ((target - asset.price) / asset.price) * 100
  return {
    ticker: asset.ticker,
    name: asset.name,
    currentPrice: asset.price,
    targetPrice: target,
    horizonDays: 30,
    confidence: Number((68 + rand() * 26).toFixed(1)),
    direction: expectedReturn > 1 ? "up" : expectedReturn < -1 ? "down" : "neutral",
    expectedReturn: Number(expectedReturn.toFixed(2)),
    model: "TFT-v3",
    history,
    predicted,
    upperBand,
    lowerBand,
    updatedAt: new Date().toISOString(),
  }
}

export const SIGNALS: Signal[] = [
  {
    id: "s1",
    ticker: "NVDA",
    name: "NVIDIA Corp.",
    action: "BUY",
    confidence: 91.2,
    expectedReturn: 8.4,
    horizon: "30d",
    reason: "Strong momentum, AI demand surge and bullish TFT forecast.",
    createdAt: new Date().toISOString(),
  },
  {
    id: "s2",
    ticker: "BTC",
    name: "Bitcoin",
    action: "BUY",
    confidence: 84.6,
    expectedReturn: 6.1,
    horizon: "14d",
    reason: "ETF inflows accelerating, breaking key resistance level.",
    createdAt: new Date().toISOString(),
  },
  {
    id: "s3",
    ticker: "TSLA",
    name: "Tesla Inc.",
    action: "SELL",
    confidence: 76.3,
    expectedReturn: -4.8,
    horizon: "21d",
    reason: "Weak delivery numbers and bearish technical pattern detected.",
    createdAt: new Date().toISOString(),
  },
  {
    id: "s4",
    ticker: "GOLD",
    name: "Gold",
    action: "HOLD",
    confidence: 69.9,
    expectedReturn: 1.2,
    horizon: "30d",
    reason: "Range-bound, awaiting Fed rate decision for direction.",
    createdAt: new Date().toISOString(),
  },
  {
    id: "s5",
    ticker: "AAPL",
    name: "Apple Inc.",
    action: "BUY",
    confidence: 82.1,
    expectedReturn: 5.3,
    horizon: "30d",
    reason: "Services growth and upcoming product cycle support upside.",
    createdAt: new Date().toISOString(),
  },
]

const longReport = `## Executive Summary

Our Temporal Fusion Transformer (TFT) model, combined with Gemini-powered fundamental analysis, indicates a constructive outlook over the 30-day horizon. Multiple signals converge to support the thesis.

## Quantitative Signals

The TFT model assigns elevated attention weights to recent volume expansion and momentum factors. Directional accuracy on this asset over the trailing 90 days stands at 78.4%, materially above the benchmark.

## Fundamental Drivers

- Revenue trajectory remains robust with consensus upgrades over the past quarter.
- Institutional positioning has shifted net long according to flow data.
- Macro backdrop is supportive with easing liquidity conditions.

## Risk Factors

While the base case is constructive, investors should monitor:

1. Broader market volatility and risk-off rotations.
2. Sector-specific regulatory developments.
3. Earnings surprises that deviate from model expectations.

## Conclusion

We maintain a favorable stance with a defined confidence band. Position sizing should respect the model's stated uncertainty range.`

const longReportVi = `## Tóm tắt điều hành

Mô hình Temporal Fusion Transformer (TFT) của chúng tôi, kết hợp với phân tích cơ bản từ Gemini, cho thấy triển vọng tích cực trong khung 30 ngày. Nhiều tín hiệu hội tụ ủng hộ luận điểm này.

## Tín hiệu định lượng

Mô hình TFT gán trọng số chú ý cao cho sự mở rộng khối lượng gần đây và các yếu tố động lượng. Độ chính xác về hướng đi của tài sản này trong 90 ngày qua đạt 78.4%, cao hơn đáng kể so với chuẩn tham chiếu.

## Động lực cơ bản

- Quỹ đạo doanh thu vững chắc với các điều chỉnh dự báo tăng trong quý vừa qua.
- Vị thế tổ chức đã chuyển sang trạng thái mua ròng theo dữ liệu dòng tiền.
- Bối cảnh vĩ mô hỗ trợ với điều kiện thanh khoản nới lỏng.

## Yếu tố rủi ro

Dù kịch bản cơ sở tích cực, nhà đầu tư nên theo dõi:

1. Biến động thị trường chung và các đợt xoay vòng né rủi ro.
2. Diễn biến pháp lý đặc thù theo ngành.
3. Bất ngờ về lợi nhuận lệch so với kỳ vọng của mô hình.

## Kết luận

Chúng tôi duy trì quan điểm tích cực với dải tin cậy xác định. Quy mô vị thế nên tôn trọng khoảng bất định mà mô hình đưa ra.`

export const RESEARCH: ResearchReport[] = [
  {
    id: "r1",
    ticker: "NVDA",
    name: "NVIDIA Corp.",
    title: "NVIDIA: AI Supercycle Far From Over",
    summary:
      "Data center demand and next-gen GPU roadmap underpin a multi-quarter bullish thesis.",
    sentiment: "bullish",
    confidence: 91,
    author: "Gemini Analyst",
    tags: ["AI", "Semiconductors", "Growth"],
    content_en: longReport,
    content_vi: longReportVi,
    translated_at: new Date().toISOString(),
    createdAt: new Date(Date.now() - 3600000).toISOString(),
    readTime: 6,
  },
  {
    id: "r2",
    ticker: "BTC",
    name: "Bitcoin",
    title: "Bitcoin: Institutional Flows Drive New Regime",
    summary: "Spot ETF adoption reshapes market structure and dampens volatility.",
    sentiment: "bullish",
    confidence: 85,
    author: "Gemini Analyst",
    tags: ["Crypto", "Macro", "ETF"],
    content_en: longReport,
    createdAt: new Date(Date.now() - 7200000).toISOString(),
    readTime: 5,
  },
  {
    id: "r3",
    ticker: "TSLA",
    name: "Tesla Inc.",
    title: "Tesla: Margin Pressure Clouds Near-Term Outlook",
    summary: "Pricing competition and delivery softness warrant a cautious stance.",
    sentiment: "bearish",
    confidence: 76,
    author: "Gemini Analyst",
    tags: ["EV", "Autos", "Margins"],
    content_en: longReport,
    content_vi: longReportVi,
    translated_at: new Date().toISOString(),
    createdAt: new Date(Date.now() - 10800000).toISOString(),
    readTime: 7,
  },
  {
    id: "r4",
    ticker: "AAPL",
    name: "Apple Inc.",
    title: "Apple: Services Engine Powers Steady Compounding",
    summary: "High-margin services offset hardware cyclicality, supporting valuation.",
    sentiment: "neutral",
    confidence: 72,
    author: "Gemini Analyst",
    tags: ["Tech", "Services", "Quality"],
    content_en: longReport,
    createdAt: new Date(Date.now() - 14400000).toISOString(),
    readTime: 5,
  },
]

export function buildPortfolio(): Portfolio {
  const positions = [
    { ticker: "BTC", qty: 0.42, avg: 58200 },
    { ticker: "NVDA", qty: 120, avg: 98.4 },
    { ticker: "AAPL", qty: 80, avg: 188.2 },
    { ticker: "ETH", qty: 6.5, avg: 3100 },
  ]
  const holdings = positions.map((p) => {
    const asset = MARKET_ASSETS.find((a) => a.ticker === p.ticker)
    const price = asset ? asset.price : p.avg
    const name = asset ? asset.name : p.ticker
    const marketValue = p.qty * price
    const costBasis = p.qty * p.avg
    const unrealizedPnl = marketValue - costBasis
    return {
      ticker: p.ticker,
      name: name,
      quantity: p.qty,
      avgPrice: p.avg,
      currentPrice: price,
      marketValue,
      costBasis,
      unrealizedPnl,
      unrealizedPnlPercent: (unrealizedPnl / costBasis) * 100,
      allocation: 0,
    }
  })
  const invested = holdings.reduce((s, h) => s + h.marketValue, 0)
  const cash = 24820.5
  const totalValue = invested + cash
  holdings.forEach((h) => (h.allocation = (h.marketValue / invested) * 100))
  const totalCost = holdings.reduce((s, h) => s + h.costBasis, 0)
  const totalPnl = invested - totalCost
  return {
    cash,
    totalValue,
    investedValue: invested,
    totalPnl,
    totalPnlPercent: (totalPnl / totalCost) * 100,
    dayPnl: 1284.32,
    dayPnlPercent: 1.02,
    holdings,
    history: genSeries(totalValue * 0.85, 90, 0.02, 0.0018, 4242),
  }
}

export const TRANSACTIONS: Transaction[] = [
  {
    id: "t1",
    ticker: "NVDA",
    action: "BUY",
    quantity: 20,
    price: 124.1,
    total: 2482,
    source: "auto",
    createdAt: new Date(Date.now() - 1800000).toISOString(),
  },
  {
    id: "t2",
    ticker: "BTC",
    action: "BUY",
    quantity: 0.05,
    price: 66800,
    total: 3340,
    source: "manual",
    createdAt: new Date(Date.now() - 5400000).toISOString(),
  },
  {
    id: "t3",
    ticker: "TSLA",
    action: "SELL",
    quantity: 15,
    price: 185.4,
    total: 2781,
    source: "auto",
    createdAt: new Date(Date.now() - 9000000).toISOString(),
  },
  {
    id: "t4",
    ticker: "AAPL",
    action: "BUY",
    quantity: 30,
    price: 210.5,
    total: 6315,
    source: "manual",
    createdAt: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: "t5",
    ticker: "ETH",
    action: "BUY",
    quantity: 2,
    price: 3420,
    total: 6840,
    source: "auto",
    createdAt: new Date(Date.now() - 172800000).toISOString(),
  },
]

export const AUTO_TRADE_CONFIG: AutoTradeConfig = {
  enabled: true,
  strategy: "balanced",
  maxPositionSize: 15,
  minConfidence: 80,
  assets: ["BTC", "ETH", "NVDA", "AAPL"],
  stopLoss: 8,
  takeProfit: 20,
}

export const AUTO_TRADE_STATS: AutoTradeStats = {
  totalTrades: 248,
  winRate: 67.3,
  totalReturn: 23.8,
  activePositions: 4,
  pnl: 8421.32,
}

export const ADMIN_USERS: AdminUser[] = [
  {
    id: "u1",
    name: "Alex Chen",
    email: "alex@forecastai.io",
    role: "admin",
    status: "active",
    portfolioValue: 124820,
    joinedAt: "2024-01-12",
    lastActive: "2m ago",
  },
  {
    id: "u2",
    name: "Maria Lopez",
    email: "maria@gmail.com",
    role: "user",
    status: "active",
    portfolioValue: 48210,
    joinedAt: "2024-03-04",
    lastActive: "1h ago",
  },
  {
    id: "u3",
    name: "James Wright",
    email: "james@outlook.com",
    role: "user",
    status: "suspended",
    portfolioValue: 8120,
    joinedAt: "2024-05-21",
    lastActive: "3d ago",
  },
  {
    id: "u4",
    name: "Yuki Tanaka",
    email: "yuki@proton.me",
    role: "user",
    status: "active",
    portfolioValue: 92340,
    joinedAt: "2024-02-18",
    lastActive: "12m ago",
  },
  {
    id: "u5",
    name: "Sam Patel",
    email: "sam@forecastai.io",
    role: "admin",
    status: "active",
    portfolioValue: 210400,
    joinedAt: "2023-11-30",
    lastActive: "just now",
  },
]

export const MODEL_ACCURACY: ModelAccuracy[] = [
  "BTC",
  "ETH",
  "NVDA",
  "AAPL",
  "TSLA",
].map((ticker, i) => ({
  model: "TFT-v3",
  ticker,
  accuracy: Number((72 + i * 2.4 + (i % 2)).toFixed(1)),
  mae: Number((1.2 + i * 0.3).toFixed(2)),
  rmse: Number((1.8 + i * 0.4).toFixed(2)),
  directionAccuracy: Number((68 + i * 2.1).toFixed(1)),
  predictions: 1200 + i * 240,
  trend: genSeries(70 + i * 2, 30, 0.02, 0.0008, 500 + i).map((p) => ({
    time: p.time,
    value: Number(Math.min(95, p.value).toFixed(1)),
  })),
}))

export const SYSTEM_METRICS: SystemMetric[] = [
  { label: "API Latency", value: 84, unit: "ms", status: "healthy" },
  { label: "Model Inference", value: 312, unit: "ms", status: "healthy" },
  { label: "DB Connections", value: 78, unit: "%", status: "warning" },
  { label: "Queue Depth", value: 12, unit: "jobs", status: "healthy" },
  { label: "Error Rate", value: 0.4, unit: "%", status: "healthy" },
  { label: "Uptime", value: 99.97, unit: "%", status: "healthy" },
]

export const RESEARCH_QUEUE: ResearchQueueItem[] = [
  {
    id: "q1",
    ticker: "NVDA",
    status: "completed",
    requestedBy: "maria@gmail.com",
    progress: 100,
    createdAt: new Date(Date.now() - 600000).toISOString(),
  },
  {
    id: "q2",
    ticker: "SOL",
    status: "processing",
    requestedBy: "yuki@proton.me",
    progress: 62,
    createdAt: new Date(Date.now() - 300000).toISOString(),
  },
  {
    id: "q3",
    ticker: "META",
    status: "pending",
    requestedBy: "sam@forecastai.io",
    progress: 0,
    createdAt: new Date(Date.now() - 120000).toISOString(),
  },
  {
    id: "q4",
    ticker: "AMZN",
    status: "failed",
    requestedBy: "james@outlook.com",
    progress: 38,
    createdAt: new Date(Date.now() - 900000).toISOString(),
  },
]
