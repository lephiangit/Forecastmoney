"use client"

import { useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { ArrowLeft, Sparkles, Filter, Search, Calendar, ChevronLeft, ChevronRight } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { Skeleton, ErrorCard, EmptyState } from "@/components/ui/states"
import { SentimentBadge, ConfidencePill } from "@/components/ui/tags"
import { timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function ResearchHistoryPage() {
  const t = useT()
  const [ticker, setTicker] = useState("")
  const [sentiment, setSentiment] = useState("")
  const [page, setPage] = useState(1)
  const limit = 20
  const offset = (page - 1) * limit

  // Debounced filter states for actual querying
  const [activeTicker, setActiveTicker] = useState("")
  const [activeSentiment, setActiveSentiment] = useState("")

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["researchHistory", limit, offset, activeTicker, activeSentiment],
    queryFn: () => api.getResearchHistory({ 
      limit, 
      offset, 
      ticker: activeTicker || undefined, 
      sentiment: activeSentiment || undefined 
    }),
  })

  function handleFilter(e: React.FormEvent) {
    e.preventDefault()
    setActiveTicker(ticker)
    setActiveSentiment(sentiment)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/research"
            className="mb-2 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("researchCenter") || "Research Center"}
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Calendar className="h-6 w-6 text-primary" />
            Research Archive
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Browse historical AI analysis and market sentiment.</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <form onSubmit={handleFilter} className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Ticker Symbol</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="e.g. BTC-USD, AAPL"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className="w-full rounded-md border border-border bg-secondary/50 py-2 pl-9 pr-3 text-sm text-foreground outline-none transition-colors focus:border-primary/50"
              />
            </div>
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Sentiment</label>
            <select
              value={sentiment}
              onChange={(e) => setSentiment(e.target.value)}
              className="w-full rounded-md border border-border bg-secondary/50 py-2 pl-3 pr-8 text-sm text-foreground outline-none transition-colors focus:border-primary/50 appearance-none"
            >
              <option value="">All</option>
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>
          <button
            type="submit"
            className="flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Filter className="h-4 w-4" /> Filter
          </button>
        </form>
      </div>

      {isError ? (
        <ErrorCard onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No historical reports found" icon={Sparkles} />
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-secondary/50 text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Asset</th>
                  <th className="px-4 py-3 font-medium">Sentiment</th>
                  <th className="px-4 py-3 font-medium">Confidence</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {data.items.map((report) => (
                  <tr key={report.id} className="transition-colors hover:bg-secondary/20">
                    <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                      {new Date(report.createdAt).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Link href={`/research/${report.ticker}`} className="font-semibold text-foreground hover:text-primary transition-colors">
                        {report.ticker}
                      </Link>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <SentimentBadge sentiment={report.sentiment} label={t(report.sentiment)} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="w-24">
                        <ConfidencePill value={report.confidence} />
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-muted-foreground truncate max-w-xs">
                      {report.summary}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Showing {data.items.length} records
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm font-medium">{page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={data.items.length < limit}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
