"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowUpRight } from "lucide-react"
import type { Signal } from "@/lib/types"
import { ActionBadge, ConfidencePill } from "@/components/ui/tags"
import { cn } from "@/lib/utils"
import { formatPercent } from "@/lib/format"

export function SignalCard({ signal, index = 0 }: { signal: Signal; index?: number }) {
  const pos = signal.expectedReturn >= 0
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      whileHover={{ y: -3 }}
    >
      <Link
        href={`/forecast/${signal.ticker}`}
        className="group block rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/40"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-base font-bold text-card-foreground">{signal.ticker}</span>
            <ActionBadge action={signal.action} />
          </div>
          <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
        </div>
        <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{signal.reason}</p>
        <div className="mt-3 flex items-center justify-between">
          <ConfidencePill value={signal.confidence} />
          <div className="text-right">
            <span className={cn("font-mono text-sm font-semibold", pos ? "text-positive" : "text-negative")}>
              {formatPercent(signal.expectedReturn)}
            </span>
            <p className="text-[10px] text-muted-foreground">{signal.horizon}</p>
          </div>
        </div>
      </Link>
    </motion.div>
  )
}
