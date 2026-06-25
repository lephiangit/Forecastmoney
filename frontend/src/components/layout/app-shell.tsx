"use client"

import { usePathname } from "next/navigation"
import type { ReactNode } from "react"
import { Navbar } from "./navbar"
import { MarketTicker } from "./market-ticker"
import { AiCopilot } from "./ai-copilot"
import { Footer } from "./footer"

const BARE_ROUTES = ["/login", "/register"]

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const bare = BARE_ROUTES.includes(pathname)

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
