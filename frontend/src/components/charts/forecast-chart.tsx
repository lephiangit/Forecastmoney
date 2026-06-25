"use client"

import { useEffect, useRef } from "react"
import {
  createChart,
  LineSeries,
  AreaSeries,
  type IChartApi,
  type UTCTimestamp,
  ColorType,
  LineStyle,
} from "lightweight-charts"
import type { Forecast } from "@/lib/types"

function toTime(iso: string): UTCTimestamp {
  return (new Date(iso).getTime() / 1000) as UTCTimestamp
}

export function ForecastChart({ forecast, height = 380 }: { forecast: Forecast; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const up = forecast.direction !== "down"
    const predColor = up ? "#0ecb81" : "#f6465d"

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#707a8a",
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: {
        vertLines: { color: "rgba(43,49,57,0.4)" },
        horzLines: { color: "rgba(43,49,57,0.4)" },
      },
      rightPriceScale: { borderColor: "#2b3139" },
      timeScale: { borderColor: "#2b3139", timeVisible: false },
      crosshair: { mode: 1 },
    })

    // Confidence band (upper + lower as faint areas)
    const upper = chart.addSeries(AreaSeries, {
      lineColor: "rgba(56,97,251,0.25)",
      topColor: "rgba(56,97,251,0.12)",
      bottomColor: "rgba(56,97,251,0.02)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    upper.setData(forecast.upperBand.map((d) => ({ time: toTime(d.time), value: d.value })))

    const lower = chart.addSeries(LineSeries, {
      color: "rgba(56,97,251,0.3)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    lower.setData(forecast.lowerBand.map((d) => ({ time: toTime(d.time), value: d.value })))

    // Historical line
    const hist = chart.addSeries(LineSeries, {
      color: "#eaecef",
      lineWidth: 2,
      priceLineVisible: false,
    })
    hist.setData(forecast.history.map((d) => ({ time: toTime(d.time), value: d.value })))

    // Predicted line (dashed)
    const pred = chart.addSeries(LineSeries, {
      color: predColor,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
    })
    const bridge = [
      { time: toTime(forecast.history[forecast.history.length - 1].time), value: forecast.history[forecast.history.length - 1].value },
      ...forecast.predicted.map((d) => ({ time: toTime(d.time), value: d.value })),
    ]
    pred.setData(bridge)

    chart.timeScale().fitContent()

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) chart.applyOptions({ width: w })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [forecast, height])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
