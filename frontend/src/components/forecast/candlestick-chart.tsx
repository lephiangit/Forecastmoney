"use client"

import { useMemo } from "react"
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { Asset, Candle } from "@/lib/forecast-data"
import { formatPrice } from "@/lib/forecast-data"

type Props = {
  asset: Asset
  candles: Candle[]
  forecastStartDate: string
}

type Row = Candle & { range: [number, number] }

export function CandlestickChart({ asset, candles, forecastStartDate }: Props) {
  const data = useMemo<Row[]>(
    () => candles.map((c) => ({ ...c, range: [c.low, c.high] })),
    [candles],
  )

  const decimals = asset.price >= 1000 ? 0 : 2
  const fmtAxis = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(decimals)}`
  const fmtDay = (d: string) => d.slice(5)

  const lows = data.map((d) => d.low)
  const highs = data.map((d) => d.high)
  const min = Math.min(...lows)
  const max = Math.max(...highs)
  const pad = (max - min) * 0.05

  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="mb-3">
        <h2 className="text-base font-semibold">Forecast Candlesticks</h2>
        <p className="text-xs text-muted-foreground">
          Per-session OHLC — solid candles are historical, dashed translucent
          candles are AI-projected
        </p>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-3 rounded-sm bg-up" /> Up session
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-3 rounded-sm bg-down" /> Down session
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-3 rounded-sm border border-dashed border-muted-foreground bg-up/40" />
          AI forecast (translucent)
        </span>
      </div>

      <div className="h-[300px] w-full sm:h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            barCategoryGap="20%"
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDay}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              minTickGap={28}
            />
            <YAxis
              domain={[min - pad, max + pad]}
              tickFormatter={fmtAxis}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={56}
            />
            <Tooltip
              content={<CandleTooltip asset={asset} />}
              cursor={{ fill: "var(--muted-foreground)", fillOpacity: 0.06 }}
            />
            <ReferenceLine
              x={forecastStartDate}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              label={{
                value: "Forecast",
                position: "insideTopRight",
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />
            <Bar
              dataKey="range"
              shape={<CandleShape />}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props
  const candle: Row = payload
  if (!candle || height <= 0) return null

  const { open, close, high, low, forecast } = candle
  const span = high - low || 1
  const pxPerPrice = height / span

  const bullish = close >= open
  const color = bullish ? "var(--up)" : "var(--down)"
  const opacity = forecast ? 0.55 : 1

  const cx = x + width / 2
  const bodyWidth = Math.max(width * 0.7, 2)
  const bodyX = cx - bodyWidth / 2

  const openY = y + (high - open) * pxPerPrice
  const closeY = y + (high - close) * pxPerPrice
  const bodyTop = Math.min(openY, closeY)
  const bodyHeight = Math.max(Math.abs(openY - closeY), 1)

  return (
    <g opacity={opacity}>
      {/* wick */}
      <line
        x1={cx}
        x2={cx}
        y1={y}
        y2={y + height}
        stroke={color}
        strokeWidth={1.5}
      />
      {/* body */}
      <rect
        x={bodyX}
        y={bodyTop}
        width={bodyWidth}
        height={bodyHeight}
        fill={forecast ? "transparent" : color}
        stroke={color}
        strokeWidth={forecast ? 1.5 : 1}
        strokeDasharray={forecast ? "3 2" : undefined}
        rx={1}
      />
      {forecast && (
        <rect
          x={bodyX}
          y={bodyTop}
          width={bodyWidth}
          height={bodyHeight}
          fill={color}
          fillOpacity={0.25}
          rx={1}
        />
      )}
    </g>
  )
}

function CandleTooltip({ active, payload, asset }: any) {
  if (!active || !payload?.length) return null
  const c: Row = payload[0]?.payload
  if (!c) return null
  const change = ((c.close - c.open) / c.open) * 100

  return (
    <div className="rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-lg backdrop-blur">
      <p className="mb-1.5 flex items-center gap-2 font-medium text-popover-foreground">
        {c.date}
        {c.forecast && (
          <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
            AI
          </span>
        )}
      </p>
      <CandleRow label="Open">{formatPrice(c.open, asset)}</CandleRow>
      <CandleRow label="High">{formatPrice(c.high, asset)}</CandleRow>
      <CandleRow label="Low">{formatPrice(c.low, asset)}</CandleRow>
      <CandleRow label="Close">{formatPrice(c.close, asset)}</CandleRow>
      <CandleRow label="Change">
        <span className={change >= 0 ? "text-up" : "text-down"}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(2)}%
        </span>
      </CandleRow>
    </div>
  )
}

function CandleRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-6">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium tabular-nums">{children}</span>
    </div>
  )
}
