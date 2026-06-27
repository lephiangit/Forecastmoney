"use client"

interface SparklineProps {
  data: number[]
  positive?: boolean
  width?: number
  height?: number
  className?: string
}

export function Sparkline({
  data,
  positive = true,
  width = 120,
  height = 30,
  className,
}: SparklineProps) {
  if (!data || !data.length) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const stepX = width / (data.length - 1)
  const points = data
    .map((d, i) => `${(i * stepX).toFixed(2)},${(height - ((d - min) / range) * height).toFixed(2)}`)
    .join(" ")
  const color = positive ? "var(--positive)" : "var(--negative)"
  const id = `spark-${positive ? "p" : "n"}-${data[0]}`
  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <polygon points={`0,${height} ${points} ${width},${height}`} fill={`url(#${id})`} />
    </svg>
  )
}
