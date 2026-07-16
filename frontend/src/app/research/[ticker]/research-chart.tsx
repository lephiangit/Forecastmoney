"use client"

import { useMemo } from "react"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { useT } from "@/lib/store"

interface ResearchChartProps {
  sentiment: string
  confidence: number
}

export function ResearchChart({ sentiment, confidence }: ResearchChartProps) {
  const t = useT()

  // Calculate gauge data based on sentiment
  // Bullish: green, Bearish: red, Neutral: gray
  const data = useMemo(() => {
    let color = "#888888" // Neutral
    if (sentiment === "BULLISH") color = "#10b981" // Emerald 500
    if (sentiment === "BEARISH") color = "#ef4444" // Red 500

    // To make a semi-circle gauge, we need two data points: 
    // 1 for the confidence fill, 1 for the remaining empty space.
    return [
      { name: t("confidence"), value: confidence, color },
      { name: "Empty", value: 100 - confidence, color: "var(--accent)" }, // Using CSS variable for border/accent color
    ]
  }, [sentiment, confidence, t])

  return (
    <div className="relative flex flex-col items-center justify-center rounded-lg border border-border bg-secondary/20 p-6">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        AI Sentiment Gauge
      </h3>
      
      <div className="relative h-[120px] w-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="100%" // Center y at the bottom to make a semi-circle
              startAngle={180}
              endAngle={0}
              innerRadius={70}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
              cornerRadius={5}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip 
              formatter={(val: any) => [`${val}%`, t("confidence")]} 
              contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
              itemStyle={{ color: 'hsl(var(--foreground))' }}
            />
          </PieChart>
        </ResponsiveContainer>
        
        {/* Absolute center text inside the gauge */}
        <div className="absolute bottom-0 left-0 flex w-full flex-col items-center justify-end pb-2">
          <span className="text-3xl font-bold tracking-tighter" style={{ color: data[0].color }}>
            {confidence}%
          </span>
          <span className="text-xs font-semibold text-muted-foreground">
            {t(sentiment.toLowerCase() as any)}
          </span>
        </div>
      </div>
    </div>
  )
}
