"use client"

import { type ReactNode, useEffect } from "react"
import { usePathname } from "next/navigation"

import { useCurrencyStore } from "@/lib/store"
import { useBackendStatusPolling } from "@/lib/use-backend-status"
import { DemoDataBanner } from "@/components/ui/system-banners"
import { AiCopilot } from "./ai-copilot"
import { Footer } from "./footer"
import { MarketTicker } from "./market-ticker"
import { Navbar } from "./navbar"

const BARE_ROUTES = ["/login", "/register"]

/** Tỷ giá được làm mới tối đa một lần mỗi ngày — nó không đổi nhanh hơn thế. */
const EXCHANGE_RATE_TTL = 24 * 60 * 60 * 1000
const EXCHANGE_RATE_TIMEOUT = 5_000

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const bare = BARE_ROUTES.includes(pathname)
  const { lastFetched, setExchangeRate } = useCurrencyStore()

  // Vòng thăm dò trạng thái backend được gắn MỘT LẦN duy nhất ở đây.
  useBackendStatusPolling()

  useEffect(() => {
    if (Date.now() - lastFetched < EXCHANGE_RATE_TTL) return

    // AbortController + timeout: nếu không có, một API tỷ giá treo sẽ để lại
    // request lơ lửng suốt vòng đời trang.
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), EXCHANGE_RATE_TIMEOUT)

    fetch("https://open.er-api.com/v6/latest/USD", { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const rate = data?.rates?.VND
        // Kiểm tra tính hợp lý trước khi ghi đè: một giá trị rác sẽ làm sai
        // toàn bộ số tiền hiển thị ở chế độ VND.
        if (typeof rate === "number" && rate > 1000 && rate < 100_000) {
          setExchangeRate(rate)
        }
      })
      .catch(() => {
        // Không lấy được tỷ giá không phải lỗi nghiêm trọng — giá trị đã lưu
        // trước đó vẫn dùng được. Im lặng bỏ qua thay vì làm bẩn console.
      })
      .finally(() => clearTimeout(timeout))

    return () => {
      clearTimeout(timeout)
      controller.abort()
    }
  }, [lastFetched, setExchangeRate])

  if (bare) {
    return <main className="min-h-screen">{children}</main>
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Bỏ qua điều hướng: người dùng bàn phím không phải tab qua toàn bộ
          menu và dải giá chạy ngang mới tới được nội dung chính. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:font-medium focus:text-primary-foreground"
      >
        Tới nội dung chính
      </a>

      <Navbar />
      <DemoDataBanner />
      <MarketTicker />

      <main
        id="main-content"
        className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 lg:px-6"
      >
        {children}
      </main>

      <Footer />
      <AiCopilot />
    </div>
  )
}
