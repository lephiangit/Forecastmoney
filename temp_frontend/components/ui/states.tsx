"use client"

import { AlertTriangle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useT } from "@/lib/store"

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-accent/60", className)} />
}

export function ErrorCard({ onRetry, className }: { onRetry?: () => void; className?: string }) {
  const t = useT()
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card p-8 text-center",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/15">
        <AlertTriangle className="h-6 w-6 text-destructive" />
      </div>
      <div>
        <p className="font-semibold text-card-foreground">{t("errorTitle")}</p>
        <p className="mt-1 text-sm text-muted-foreground">{t("errorBody")}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-2 rounded-md border border-border bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {t("retry")}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, icon: Icon }: { title: string; icon?: typeof AlertTriangle }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-card/50 p-10 text-center text-muted-foreground">
      {Icon && <Icon className="h-7 w-7" />}
      <p className="text-sm">{title}</p>
    </div>
  )
}
