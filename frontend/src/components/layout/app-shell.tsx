"use client"

import { usePathname } from "next/navigation"
import { type ReactNode, useEffect } from "react"
import { useCurrencyStore } from "@/lib/store"
import { Navbar } from "./navbar"
import { MarketTicker } from "./market-ticker"
import { AiCopilot } from "./ai-copilot"
import { Footer } from "./footer"

const BARE_ROUTES = ["/login", "/register"]

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const bare = BARE_ROUTES.includes(pathname)
  const { lastFetched, setExchangeRate } = useCurrencyStore()

  useEffect(() => {
    // Check if we need to fetch the exchange rate (older than 24 hours)
    const ONE_DAY = 24 * 60 * 60 * 1000
    if (Date.now() - lastFetched > ONE_DAY) {
      fetch("https://open.er-api.com/v6/latest/USD")
        .then((res) => res.json())
        .then((data) => {
          if (data && data.rates && data.rates.VND) {
            setExchangeRate(data.rates.VND)
          }
        })
        .catch((err) => console.error("Failed to fetch exchange rate:", err))
    }
  }, [lastFetched, setExchangeRate])

  if (bare) {
    return <main className="min-h-screen">{children}</main>
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <MarketTicker />
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 lg:px-6">{children}</main>
      <Footer />
      <AiCopilot />
    </div>
  )
}
