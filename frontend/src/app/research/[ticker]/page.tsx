"use client"

import { use, useState } from "react"
import Link from "next/link"
import { useQuery, useMutation } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { ArrowLeft, Sparkles, Clock, Languages, Loader2, TrendingUp, BarChart3, Check } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { Skeleton, ErrorCard, EmptyState } from "@/components/ui/states"
import { SentimentBadge, ConfidencePill } from "@/components/ui/tags"
import { Markdown } from "@/components/ui/markdown"
import { timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function ResearchDetailPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params)
  const symbol = decodeURIComponent(ticker).toUpperCase()
  const t = useT()
  const [view, setView] = useState<"en" | "vi">("en")
  const [translated, setTranslated] = useState<string | null>(null)

  const { data: report, isError, refetch, isLoading } = useQuery({
    queryKey: ["research", symbol],
    queryFn: () => api.getResearchReport(symbol),
  })

  const translateMut = useMutation({
    mutationFn: () => api.translateReport(report!.id),
    onSuccess: (res) => {
      setTranslated(res.content_vi)
      setView("vi")
    },
  })

  function handleVi() {
    if (!report) return
    if (report.content_vi || translated) {
      setView("vi")
    } else {
      translateMut.mutate()
    }
  }

  const viContent = report?.content_vi ?? translated
  const body = view === "vi" ? viContent ?? report?.content_en ?? "" : report?.content_en ?? ""

  return (
    <div>
      <Link
        href="/research"
        className="mb-4 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("researchCenter")}
      </Link>

      {isError ? (
        <ErrorCard onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-96" />
        </div>
      ) : !report ? (
        <EmptyState title={`No research report for ${symbol}.`} icon={Sparkles} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
          <motion.article
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="rounded-lg border border-border bg-card p-6 sm:p-8"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                {report.ticker.slice(0, 3)}
              </span>
              <span className="font-mono text-sm font-bold text-card-foreground">{report.ticker}</span>
              <SentimentBadge sentiment={report.sentiment} label={t(report.sentiment)} />
            </div>

            <h1 className="mt-4 text-2xl font-bold tracking-tight text-card-foreground text-balance">
              {report.title}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">{report.summary}</p>

            <div className="mt-4 flex flex-wrap items-center gap-4 border-y border-border py-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> {report.author}
              </span>
              <span className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" /> {report.readTime} {t("readTime")}
              </span>
              <span>{timeAgo(report.createdAt)}</span>
            </div>

            {/* Language toggle */}
            <div className="mt-5 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{t("readReport")}:</span>
              <div className="inline-flex overflow-hidden rounded-md border border-border">
                <button
                  onClick={() => setView("en")}
                  className={cn(
                    "px-3 py-1.5 text-xs font-semibold transition-colors",
                    view === "en" ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
                  )}
                >
                  EN
                </button>
                <button
                  onClick={handleVi}
                  disabled={translateMut.isPending}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition-colors",
                    view === "vi" ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
                  )}
                >
                  {translateMut.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Languages className="h-3 w-3" />
                  )}
                  VI
                </button>
              </div>
              {view === "vi" && (viContent || report.content_vi) && (
                <span className="flex items-center gap-1 text-[11px] text-info">
                  <Check className="h-3 w-3" /> Translated by Gemini
                </span>
              )}
            </div>

            <div className="mt-5">
              <Markdown content={body} />
            </div>
          </motion.article>

          <aside className="space-y-4">
            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="text-sm font-semibold text-card-foreground">{t("aiPrediction")}</h3>
              <div className="mt-4 space-y-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("sentiment")}</p>
                  <div className="mt-1.5">
                    <SentimentBadge sentiment={report.sentiment} label={t(report.sentiment)} />
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("confidence")}</p>
                  <div className="mt-2">
                    <ConfidencePill value={report.confidence} />
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="text-sm font-semibold text-card-foreground">Tags</h3>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(Array.isArray(report.tags) ? report.tags : typeof report.tags === 'string' ? report.tags.split(',') : []).map((tag: string) => (
                  <span key={tag} className="rounded bg-secondary px-2 py-1 text-[11px] font-medium text-muted-foreground">
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Link
                href={`/forecast/${report.ticker}`}
                className="flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
              >
                <TrendingUp className="h-4 w-4" /> {t("forecast")} {report.ticker}
              </Link>
              <Link
                href={`/markets`}
                className="flex items-center justify-center gap-2 rounded-md border border-border bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-accent"
              >
                <BarChart3 className="h-4 w-4" /> {t("markets")}
              </Link>
            </div>

            {report.headlines && report.headlines.length > 0 && (
              <div className="mt-8 rounded-lg border border-border bg-secondary/50 p-5">
                <h3 className="mb-4 text-sm font-semibold text-card-foreground">Nguồn tham khảo (Reference Links)</h3>
                <ul className="space-y-3">
                  {report.headlines.map((headline, idx) => (
                    <li key={idx} className="text-sm">
                      <a 
                        href={headline.link} 
                        target="_blank" 
                        rel="noreferrer"
                        className="font-medium text-primary hover:underline"
                      >
                        {headline.title}
                      </a>
                      <span className="ml-2 text-xs text-muted-foreground">- {headline.source}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
