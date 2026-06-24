"use client"

import { useMemo, useState } from "react"
import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { RotateCcw } from "lucide-react"
import type { Asset, PricePoint } from "@/lib/forecast-data"
import { formatPrice } from "@/lib/forecast-data"

type Props = {
  asset: Asset
  points: PricePoint[]
  forecastStartDate: string
  showSentiment: boolean
  onToggleSentiment: (v: boolean) => void
}

type Row = PricePoint & { band: [number, number] | null }

export function PriceForecastChart({
  asset,
  points,
  forecastStartDate,
  showSentiment,
  onToggleSentiment,
}: Props) {
  const data = useMemo<Row[]>(
    () =>
      points.map((p) => ({
        ...p,
        band:
          p.upper != null && p.lower != null ? [p.lower, p.upper] : null,
      })),
    [points],
  )

  const [brush, setBrush] = useState<{ start: number; end: number } | null>(
    null,
  )

  const decimals = asset.price >= 1000 ? 0 : 2
  const fmtAxis = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(decimals)}`
  const fmtDay = (d: string) => d.slice(5)

  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Price &amp; AI Forecast</h2>
          <p className="text-xs text-muted-foreground">
            Historical close with TFT median forecast and confidence band
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium">
            <input
              type="checkbox"
              checked={showSentiment}
              onChange={(e) => onToggleSentiment(e.target.checked)}
              className="accent-[var(--sentiment)]"
            />
            Sentiment
          </label>
          <button
            type="button"
            onClick={() => setBrush(null)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <RotateCcw className="size-3.5" />
            Reset zoom
          </button>
        </div>
      </div>

      <Legend showSentiment={showSentiment} />

      <div className="h-[340px] w-full sm:h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
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
              domain={["auto", "auto"]}
              tickFormatter={fmtAxis}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={56}
            />
            <Tooltip
              content={<ChartTooltip asset={asset} />}
              cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
            />

            <Area
              dataKey="band"
              stroke="none"
              fill="var(--forecast)"
              fillOpacity={0.1}
              isAnimationActive={false}
              connectNulls
            />

            <ReferenceLine
              x={forecastStartDate}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              label={{
                value: "AI Forecast",
                position: "insideTopRight",
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />

            <Line
              dataKey="historical"
              name="Historical"
              stroke="var(--foreground)"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="forecast"
              name="Forecast"
              stroke="var(--forecast)"
              strokeWidth={3}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            {showSentiment && (
              <Line
                dataKey="sentiment"
                name="Sentiment"
                stroke="var(--sentiment)"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )}

            <Brush
              dataKey="date"
              height={26}
              travellerWidth={10}
              stroke="var(--primary)"
              fill="var(--secondary)"
              tickFormatter={fmtDay}
              startIndex={brush?.start}
              endIndex={brush?.end}
              onChange={(range: any) => {
                if (
                  range &&
                  typeof range.startIndex === "number" &&
                  typeof range.endIndex === "number"
                ) {
                  setBrush({ start: range.startIndex, end: range.endIndex })
                }
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

function Legend({ showSentiment }: { showSentiment: boolean }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <LegendItem color="var(--foreground)" label="Historical" />
      <LegendItem color="var(--forecast)" label="Forecast (median)" thick />
      {showSentiment && (
        <LegendItem color="var(--sentiment)" label="Sentiment fusion" dashed />
      )}
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block h-3 w-4 rounded-sm"
          style={{ backgroundColor: "var(--forecast)", opacity: 0.2 }}
        />
        Confidence band (q10–q90)
      </span>
    </div>
  )
}

function LegendItem({
  color,
  label,
  thick,
  dashed,
}: {
  color: string
  label: string
  thick?: boolean
  dashed?: boolean
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block w-4"
        style={{
          borderTopWidth: thick ? 3 : 2,
          borderTopStyle: dashed ? "dashed" : "solid",
          borderTopColor: color,
        }}
      />
      {label}
    </span>
  )
}

function ChartTooltip({
  active,
  payload,
  label,
  asset,
}: any) {
  if (!active || !payload?.length) return null
  const row: Row = payload[0]?.payload
  if (!row) return null

  const isForecast = row.forecast != null && row.historical == null
  const price = isForecast ? row.forecast : row.historical
  const change =
    price != null ? ((price - asset.price) / asset.price) * 100 : null

  return (
    <div className="rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-lg backdrop-blur">
      <p className="mb-1.5 font-medium text-popover-foreground">{label}</p>
      <Row label={isForecast ? "Forecast" : "Historical"}>
        {price != null ? formatPrice(price, asset) : "—"}
      </Row>
      {isForecast && row.sentiment != null && (
        <Row label="Sentiment">{formatPrice(row.sentiment, asset)}</Row>
      )}
      {isForecast && row.upper != null && row.lower != null && (
        <Row label="Conf. range">
          {formatPrice(row.lower, asset)} – {formatPrice(row.upper, asset)}
        </Row>
      )}
      {change != null && (
        <Row label="vs. now">
          <span className={change >= 0 ? "text-up" : "text-down"}>
            {change >= 0 ? "+" : ""}
            {change.toFixed(2)}%
          </span>
        </Row>
      )}
    </div>
  )
}

function Row({
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
