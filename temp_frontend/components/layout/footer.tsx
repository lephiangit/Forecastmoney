"use client"

import Link from "next/link"
import { Activity } from "lucide-react"

export function Footer() {
  return (
    <footer className="mt-12 border-t border-border bg-bg-secondary">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-8 lg:flex-row lg:items-center lg:justify-between lg:px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
            <Activity className="h-4 w-4 text-primary-foreground" strokeWidth={2.5} />
          </div>
          <span className="font-bold text-foreground">
            Forecast<span className="text-primary">AI</span>
          </span>
          <span className="ml-2 text-sm text-muted-foreground">AI-Powered Market Intelligence</span>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <Link href="/markets" className="hover:text-foreground">Markets</Link>
          <Link href="/forecast" className="hover:text-foreground">Forecast</Link>
          <Link href="/research" className="hover:text-foreground">Research</Link>
          <Link href="/portfolio" className="hover:text-foreground">Portfolio</Link>
        </nav>
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} ForecastAI. Paper trading only. Not financial advice.
        </p>
      </div>
    </footer>
  )
}
