// Deterministic mock data layer for the forecast detail page.
// All values are pseudo-random but seeded by ticker so they stay stable
// across renders and horizon changes.

export type Asset = {
  ticker: string
  name: string
  kind: "crypto" | "equity"
  price: number
  change24h: number
  marketCap: string
  volume: string
}

export type PricePoint = {
  date: string
  // Only one of these is set per point so Recharts breaks the lines cleanly.
  historical: number | null
  forecast: number | null
  sentiment: number | null
  upper: number | null
  lower: number | null
}

export type Candle = {
  date: string
  open: number
  high: number
  low: number
  close: number
  forecast: boolean
}

export type Recommendation = "BUY" | "HOLD" | "SELL"

export type Kpis = {
  expectedReturn: number
  targetPrice: number
  confidence: number
  riskLevel: "Low" | "Medium" | "High"
}

export type Research = {
  summary: string
  bullish: string[]
  bearish: string[]
  newsSentiment: { label: string; score: number; sources: number }
  recommendation: Recommendation
  timeHorizon: string
  generatedAt: string
}

const ASSETS: Record<string, Asset> = {
  BTC: {
    ticker: "BTC",
    name: "Bitcoin",
    kind: "crypto",
    price: 107542,
    change24h: 2.43,
    marketCap: "$2.1T",
    volume: "$48.3B",
  },
  ETH: {
    ticker: "ETH",
    name: "Ethereum",
    kind: "crypto",
    price: 3984,
    change24h: -1.12,
    marketCap: "$478.9B",
    volume: "$21.7B",
  },
  SOL: {
    ticker: "SOL",
    name: "Solana",
    kind: "crypto",
    price: 214.6,
    change24h: 4.87,
    marketCap: "$98.4B",
    volume: "$6.1B",
  },
  AAPL: {
    ticker: "AAPL",
    name: "Apple Inc.",
    kind: "equity",
    price: 232.18,
    change24h: 0.74,
    marketCap: "$3.5T",
    volume: "$9.8B",
  },
  NVDA: {
    ticker: "NVDA",
    name: "NVIDIA Corporation",
    kind: "equity",
    price: 138.42,
    change24h: 3.21,
    marketCap: "$3.4T",
    volume: "$28.4B",
  },
  TSLA: {
    ticker: "TSLA",
    name: "Tesla, Inc.",
    kind: "equity",
    price: 421.06,
    change24h: -2.18,
    marketCap: "$1.3T",
    volume: "$18.2B",
  },
}

export const AVAILABLE_TICKERS = Object.keys(ASSETS)

// Mulberry32 — tiny deterministic PRNG.
function mulberry32(seed: number) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function seedFromTicker(ticker: string) {
  let h = 0
  for (let i = 0; i < ticker.length; i++) {
    h = (h << 5) - h + ticker.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h) + 1
}

export function getAsset(ticker: string): Asset | null {
  return ASSETS[ticker.toUpperCase()] ?? null
}

function fmtDate(d: Date) {
  return d.toISOString().slice(0, 10)
}

const HISTORY_DAYS = 60

type Series = {
  points: PricePoint[]
  candles: Candle[]
  forecastStartDate: string
  finalForecast: number
  finalUpper: number
  finalLower: number
}

export function buildSeries(asset: Asset, horizon: number): Series {
  const rand = mulberry32(seedFromTicker(asset.ticker) + horizon)
  const price = asset.price
  const dailyVol = (asset.kind === "crypto" ? 0.028 : 0.016) * price

  // ---- Build historical path ending at the current price ----
  const hist: number[] = []
  let p = price
  for (let i = 0; i < HISTORY_DAYS; i++) {
    hist.push(p)
    // walk backwards with mild mean reversion
    p = p - (rand() - 0.5) * dailyVol * 1.6
  }
  hist.reverse()
  // normalize so the last historical point equals the live price
  const adjust = price - hist[hist.length - 1]
  for (let i = 0; i < hist.length; i++) {
    hist[i] += adjust * (i / (hist.length - 1))
  }

  const today = new Date()
  const points: PricePoint[] = []
  const candles: Candle[] = []

  // historical points + candles
  let prevClose = hist[0] * 0.99
  for (let i = 0; i < HISTORY_DAYS; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - (HISTORY_DAYS - 1 - i))
    const date = fmtDate(d)
    const close = hist[i]
    points.push({
      date,
      historical: round(close),
      forecast: null,
      sentiment: null,
      upper: null,
      lower: null,
    })
    const open = prevClose
    const wick = dailyVol * 0.7
    const high = Math.max(open, close) + rand() * wick
    const low = Math.min(open, close) - rand() * wick
    candles.push({
      date,
      open: round(open),
      high: round(high),
      low: round(low),
      close: round(close),
      forecast: false,
    })
    prevClose = close
  }

  // ---- Build forecast path ----
  // Pick an overall drift direction biased by ticker seed.
  const driftBias = (rand() - 0.42) * dailyVol * 0.6
  const forecastStartDate = points[points.length - 1].date

  // connect the forecast line to the last historical point
  points[points.length - 1].forecast = points[points.length - 1].historical
  points[points.length - 1].sentiment = points[points.length - 1].historical
  points[points.length - 1].upper = points[points.length - 1].historical
  points[points.length - 1].lower = points[points.length - 1].historical

  let fc = price
  let sent = price
  prevClose = price
  for (let i = 1; i <= horizon; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    const date = fmtDate(d)

    fc = fc + driftBias + (rand() - 0.5) * dailyVol
    sent = sent + driftBias * 1.15 + (rand() - 0.5) * dailyVol * 1.1

    // widening confidence band with horizon
    const spread = dailyVol * Math.sqrt(i) * 1.3
    const upper = fc + spread
    const lower = fc - spread

    points.push({
      date,
      historical: null,
      forecast: round(fc),
      sentiment: round(sent),
      upper: round(upper),
      lower: round(lower),
    })

    const open = prevClose
    const wick = dailyVol * 0.6
    const high = Math.max(open, fc) + rand() * wick
    const low = Math.min(open, fc) - rand() * wick
    candles.push({
      date,
      open: round(open),
      high: round(high),
      low: round(low),
      close: round(fc),
      forecast: true,
    })
    prevClose = fc
  }

  const last = points[points.length - 1]
  return {
    points,
    candles,
    forecastStartDate,
    finalForecast: last.forecast as number,
    finalUpper: last.upper as number,
    finalLower: last.lower as number,
  }
}

export function buildKpis(asset: Asset, series: Series): Kpis {
  const expectedReturn =
    ((series.finalForecast - asset.price) / asset.price) * 100
  const rand = mulberry32(seedFromTicker(asset.ticker) + 7)
  const confidence = Math.round(58 + rand() * 36) // 58 - 94
  const volatility = (series.finalUpper - series.finalLower) / series.finalForecast
  const riskLevel: Kpis["riskLevel"] =
    volatility > 0.28 ? "High" : volatility > 0.14 ? "Medium" : "Low"
  return {
    expectedReturn: round(expectedReturn, 2),
    targetPrice: series.finalForecast,
    confidence,
    riskLevel,
  }
}

export function buildResearch(
  asset: Asset,
  kpis: Kpis,
  horizon: number,
): Research {
  const up = kpis.expectedReturn >= 0
  const recommendation: Recommendation =
    kpis.expectedReturn > 4 && kpis.confidence > 70
      ? "BUY"
      : kpis.expectedReturn < -3
        ? "SELL"
        : "HOLD"

  const bullish = [
    `Momentum indicators (RSI, MACD) point to continued accumulation for ${asset.ticker}.`,
    `On-chain / order-flow data shows steady demand absorbing recent supply.`,
    `The temporal fusion model projects a ${kpis.expectedReturn >= 0 ? "+" : ""}${kpis.expectedReturn}% move over ${horizon} days.`,
    `Volatility-adjusted risk/reward remains favorable at current levels.`,
  ]
  const bearish = [
    `Broader market risk appetite could compress multiples in a drawdown.`,
    `Forecast confidence band widens materially beyond ${Math.round(horizon * 0.6)} days.`,
    `Liquidity thins out around key resistance, raising slippage risk.`,
    `Macro / rate surprises remain an unmodeled tail risk for ${asset.name}.`,
  ]

  const sentimentScore = Math.round((up ? 62 : 41) + (kpis.confidence - 70) * 0.4)

  return {
    summary: `Our AI ensemble combines a Temporal Fusion Transformer price model with a news-sentiment fusion layer to project ${asset.name} (${asset.ticker}) over the next ${horizon} days. The blended outlook is ${up ? "constructive" : "cautious"}, targeting ${formatPrice(kpis.targetPrice, asset)} with ${kpis.confidence}% model confidence and ${kpis.riskLevel.toLowerCase()} risk.`,
    bullish,
    bearish,
    newsSentiment: {
      label: sentimentScore >= 60 ? "Bullish" : sentimentScore >= 45 ? "Neutral" : "Bearish",
      score: Math.max(0, Math.min(100, sentimentScore)),
      sources: 120 + (seedFromTicker(asset.ticker) % 280),
    },
    recommendation,
    timeHorizon: `${horizon} days`,
    generatedAt: new Date().toISOString(),
  }
}

function round(n: number, dp = 2) {
  const f = Math.pow(10, dp)
  return Math.round(n * f) / f
}

export function formatPrice(value: number, asset: Asset) {
  const decimals = asset.price >= 1000 ? 0 : 2
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}
