"use client"

import { motion } from "framer-motion"
import { TrendingUp, TrendingDown, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { CountUp } from "./count-up"

interface StatCardProps {
  label: string
  value: number
  format?: (n: number) => string
  changePercent?: number
  icon?: LucideIcon
  accent?: boolean
  delay?: number
}

export function StatCard({ label, value, format, changePercent, icon: Icon, accent, delay = 0 }: StatCardProps) {
  const isPos = (changePercent ?? 0) >= 0
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      whileHover={{ y: -3 }}
      className={cn(
        "rounded-lg border border-border bg-card p-4 transition-colors hover:border-muted-foreground/40 sm:p-5",
        accent && "border-primary/30",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
        {Icon && <Icon className={cn("h-4 w-4", accent ? "text-primary" : "text-muted-foreground")} />}
      </div>
      <div className="mt-2 font-mono text-2xl font-semibold tracking-tight text-card-foreground">
        <CountUp value={value} format={format} />
      </div>
      {changePercent !== undefined && (
        <div className={cn("mt-1.5 flex items-center gap-1 text-sm font-medium", isPos ? "text-positive" : "text-negative")}>
          {isPos ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
          <CountUp value={Math.abs(changePercent)} decimals={2} suffix="%" />
        </div>
      )}
    </motion.div>
  )
}
