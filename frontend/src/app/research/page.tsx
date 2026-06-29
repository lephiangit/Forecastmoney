"use client"

import { useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Search, Clock, ArrowUpRight, Sparkles, Languages } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import type { TranslationKey } from "@/lib/i18n"
import { PageHeader } from "@/components/ui/page-header"
import { Skeleton, ErrorCard, EmptyState } from "@/components/ui/states"
import { SentimentBadge, ConfidencePill } from "@/components/ui/tags"
import { timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

const FILTERS: { value: string; key: TranslationKey }[] = [
  { value: "all", key: "allAssets" },
  { value: "bullish", key: "bullish" },
  { value: "bearish", key: "bearish" },
  { value: "neutral", key: "neutral" },
]

export default function ResearchPage() {
  const t = useT()
  const [filter, setFilter] = useState("all")
  const [search, setSearch] = useState("")
  const { data, isError, refetch } = useQuery({ queryKey: ["research"], queryFn: api.getResearch })

  const filtered = (data ?? [])
    .filter((r) => filter === "all" || r.sentiment === filter)
    .filter(
      (r) =>
        r.title.toLowerCase().includes(search.toLowerCase()) ||
        r.ticker.toLowerCase().includes(search.toLowerCase()),
    )

  return (
    <div>
      <PageHeader title={t("researchCenter")} subtitle={t("whyAiThinks")} />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                filter === f.value
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-secondary text-muted-foreground hover:text-foreground",
              )}
            >
              {t(f.key)}
            </button>
          ))}
          <span className="mx-1 h-5 w-px bg-border"></span>
          <Link
            href="/research/history"
            className="flex items-center gap-2 rounded-md border border-primary/50 bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            📚 View Archive
          </Link>
        </div>
        <div className="relative sm:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchAssets")}
            className="w-full rounded-md border border-border bg-secondary py-2 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/50"
          />
        </div>
      </div>

      {isError ? (
        <ErrorCard onRetry={() => refetch()} />
      ) : !data ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState title="No research reports found." icon={Sparkles} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((r, i) => (
            <motion.div
              key={r.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.05 }}
              whileHover={{ y: -3 }}
            >
              <Link
                href={`/research/${r.ticker}`}
                className="group flex h-full flex-col rounded-lg border border-border bg-card p-5 transition-colors hover:border-primary/40"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                      {r.ticker.slice(0, 3)}
                    </span>
                    <span className="font-mono text-sm font-bold text-card-foreground">{r.ticker}</span>
                  </div>
                  <SentimentBadge sentiment={r.sentiment} label={t(r.sentiment)} />
                </div>

                <h2 className="mt-3 line-clamp-2 font-semibold leading-snug text-card-foreground group-hover:text-primary">
                  {r.title}
                </h2>
                <p className="mt-2 line-clamp-2 flex-1 text-sm text-muted-foreground">{r.summary}</p>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  {r.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="rounded bg-secondary px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>

                <div className="mt-4 border-t border-border pt-3">
                  <ConfidencePill value={r.confidence} />
                </div>

                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <Sparkles className="h-3 w-3 text-primary" /> {r.author}
                    </span>
                    {r.content_vi && (
                      <span className="flex items-center gap-1 text-info">
                        <Languages className="h-3 w-3" /> VI
                      </span>
                    )}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {r.readTime} {t("readTime")}
                    </span>
                    <ArrowUpRight className="h-3.5 w-3.5 transition-colors group-hover:text-primary" />
                  </span>
                </div>
                <p className="mt-2 text-[10px] text-muted-foreground">{timeAgo(r.createdAt)}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
