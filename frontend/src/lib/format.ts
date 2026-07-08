import { useCurrencyStore } from "./store"

export function formatCurrency(value: number, opts?: { compact?: boolean; decimals?: number; currency?: string }): string {
  let v = Number(value) || 0
  
  const state = useCurrencyStore.getState()
  const globalCurrency = state.currency
  const exchangeRate = state.exchangeRate || 25400

  // Ticker base currency (VD: FPT.VN -> VND, BTC-USD -> USD)
  const isBaseVND = opts?.currency === "VND" || opts?.currency?.endsWith(".VN")

  // Logic chuyển đổi
  if (globalCurrency === "VND") {
    // Nếu hệ thống đang hiển thị VND, mà tài sản là USD -> nhân tỷ giá
    if (!isBaseVND) {
      v = v * exchangeRate
    }
  } else {
    // Nếu hệ thống đang hiển thị USD, mà tài sản là VND -> chia tỷ giá
    if (isBaseVND) {
      v = v / exchangeRate
    }
  }

  // Quyết định format đầu ra
  const isOutputVND = globalCurrency === "VND"
  const locale = isOutputVND ? "vi-VN" : "en-US"
  const currency = isOutputVND ? "VND" : "USD"

  if (opts?.compact) {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currency,
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(v)
  }
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currency,
    minimumFractionDigits: isOutputVND ? 0 : (opts?.decimals ?? 2),
    maximumFractionDigits: isOutputVND ? 0 : (opts?.decimals ?? 2),
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
