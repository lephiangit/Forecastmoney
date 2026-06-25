"use client"

import { useEffect, useRef } from "react"
import {
  createChart,
  AreaSeries,
  type IChartApi,
  type UTCTimestamp,
  ColorType,
} from "lightweight-charts"
import type { ForecastPoint } from "@/lib/types"

interface PriceChartProps {
  data: ForecastPoint[]
  positive?: boolean
  height?: number
}

function toTime(iso: string): UTCTimestamp {
  return (new Date(iso).getTime() / 1000) as UTCTimestamp
}

export function PriceChart({ data, positive = true, height = 320 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const color = positive ? "#0ecb81" : "#f6465d"
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
      handleScroll: false,
      handleScale: false,
    })
    chartRef.current = chart

    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      topColor: positive ? "rgba(14,203,129,0.25)" : "rgba(246,70,93,0.25)",
      bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2,
      priceLineVisible: false,
    })
    series.setData(data.map((d) => ({ time: toTime(d.time), value: d.value })))
    chart.timeScale().fitContent()

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) chart.applyOptions({ width: w })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, positive, height])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
