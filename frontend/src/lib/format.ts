export function formatCurrency(value: number, opts?: { compact?: boolean; decimals?: number }): string {
  const v = Number(value) || 0
  if (opts?.compact) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(v)
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: opts?.decimals ?? 2,
    maximumFractionDigits: opts?.decimals ?? 2,
  }).format(v)
}

export function formatNumber(value: number, opts?: { compact?: boolean; decimals?: number }): string {
  const v = Number(value) || 0
  return new Intl.NumberFormat("en-US", {
    notation: opts?.compact ? "compact" : "standard",
    minimumFractionDigits: 0,
    maximumFractionDigits: opts?.decimals ?? 2,
  }).format(v)
}

export function formatPercent(value: number): string {
  const v = Number(value) || 0
  const sign = v > 0 ? "+" : ""
  return `${sign}${v.toFixed(2)}%`
}

export function formatSigned(value: number): string {
  const v = Number(value) || 0
  const sign = v > 0 ? "+" : ""
  return `${sign}${formatCurrency(v)}`
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
