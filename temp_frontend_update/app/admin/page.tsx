"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Users, UserCheck, DollarSign, Server, Activity, Cpu, ListChecks } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { Sparkline } from "@/components/ui/sparkline"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { StatusDot, ConfidencePill } from "@/components/ui/tags"
import { formatCurrency, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

type Tab = "users" | "system" | "accuracy" | "queue"

export default function AdminPage() {
  const t = useT()
  const [tab, setTab] = useState<Tab>("users")

  const usersQ = useQuery({ queryKey: ["adminUsers"], queryFn: api.getAdminUsers })
  const systemQ = useQuery({ queryKey: ["systemMetrics"], queryFn: api.getSystemMetrics })
  const accuracyQ = useQuery({ queryKey: ["modelAccuracy"], queryFn: api.getModelAccuracy })
  const queueQ = useQuery({ queryKey: ["researchQueue"], queryFn: api.getResearchQueue })

  const users = usersQ.data ?? []
  const totalUsers = users.length
  const activeUsers = users.filter((u) => u.status === "active").length
  const totalAum = users.reduce((s, u) => s + u.portfolioValue, 0)

  const tabs: { value: Tab; label: string; icon: typeof Users }[] = [
    { value: "users", label: t("userManagement"), icon: Users },
    { value: "system", label: t("systemMonitoring"), icon: Server },
    { value: "accuracy", label: t("modelAccuracy"), icon: Cpu },
    { value: "queue", label: t("researchQueue"), icon: ListChecks },
  ]

  return (
    <div>
      <PageHeader title={t("adminDashboard")} subtitle={t("howIsSystem")} />

      {/* KPI overview */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label={t("totalUsers")} value={totalUsers} format={(n) => n.toFixed(0)} icon={Users} accent />
        <StatCard label={t("activeUsers")} value={activeUsers} format={(n) => n.toFixed(0)} icon={UserCheck} delay={0.05} />
        <StatCard label={t("totalAum")} value={totalAum} format={(n) => formatCurrency(n, { compact: true })} icon={DollarSign} delay={0.1} />
        <StatCard label={t("apiRequests")} value={1284932} format={(n) => n.toLocaleString("en-US")} icon={Activity} delay={0.15} />
      </div>

      {/* Tabs */}
      <div className="mt-6 flex flex-wrap gap-2 border-b border-border">
        {tabs.map((tb) => {
          const Icon = tb.icon
          return (
            <button
              key={tb.value}
              onClick={() => setTab(tb.value)}
              className={cn(
                "flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors -mb-px",
                tab === tb.value
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" /> {tb.label}
            </button>
          )
        })}
      </div>

      <div className="mt-6">
        {tab === "users" && (
          usersQ.isError ? (
            <ErrorCard onRetry={() => usersQ.refetch()} />
          ) : !usersQ.data ? (
            <Skeleton className="h-80" />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-3 font-medium">{t("user")}</th>
                    <th className="px-4 py-3 font-medium">{t("role")}</th>
                    <th className="px-4 py-3 font-medium">{t("status")}</th>
                    <th className="px-4 py-3 text-right font-medium">{t("totalValue")}</th>
                    <th className="px-4 py-3 font-medium">Joined</th>
                    <th className="px-4 py-3 text-right font-medium">{t("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <motion.tr
                      key={u.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.04 }}
                      className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground">
                            {u.name.slice(0, 2).toUpperCase()}
                          </span>
                          <div>
                            <p className="font-medium text-card-foreground">{u.name}</p>
                            <p className="text-xs text-muted-foreground">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "rounded px-2 py-0.5 text-xs font-semibold uppercase",
                          u.role === "admin" ? "bg-primary/15 text-primary" : "bg-accent text-muted-foreground",
                        )}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2 text-xs capitalize text-card-foreground">
                          <StatusDot status={u.status} /> {u.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(u.portfolioValue, { compact: true })}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{u.joinedAt}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          className={cn(
                            "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                            u.status === "active"
                              ? "border-negative/30 text-negative hover:bg-negative/10"
                              : "border-positive/30 text-positive hover:bg-positive/10",
                          )}
                        >
                          {u.status === "active" ? t("suspend") : t("activate")}
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {tab === "system" && (
          !systemQ.data ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {systemQ.data.map((m, i) => (
                <motion.div
                  key={m.label}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="rounded-lg border border-border bg-card p-5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{m.label}</span>
                    <span className="flex items-center gap-1.5 text-xs capitalize text-card-foreground">
                      <StatusDot status={m.status} /> {m.status}
                    </span>
                  </div>
                  <p className="mt-3 font-mono text-2xl font-semibold text-card-foreground">
                    {m.value}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">{m.unit}</span>
                  </p>
                </motion.div>
              ))}
            </div>
          )
        )}

        {tab === "accuracy" && (
          !accuracyQ.data ? (
            <Skeleton className="h-80" />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-3 font-medium">{t("model")}</th>
                    <th className="px-4 py-3 font-medium">{t("asset")}</th>
                    <th className="px-4 py-3 font-medium">{t("accuracy")}</th>
                    <th className="px-4 py-3 text-right font-medium">MAE</th>
                    <th className="px-4 py-3 text-right font-medium">RMSE</th>
                    <th className="px-4 py-3 text-right font-medium">Predictions</th>
                    <th className="px-4 py-3 text-right font-medium">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {accuracyQ.data.map((m, i) => (
                    <motion.tr
                      key={m.ticker}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.04 }}
                      className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/40"
                    >
                      <td className="px-4 py-3 font-mono text-muted-foreground">{m.model}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-card-foreground">{m.ticker}</td>
                      <td className="px-4 py-3"><ConfidencePill value={m.accuracy} /></td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m.mae}</td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m.rmse}</td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m.predictions.toLocaleString("en-US")}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end">
                          <Sparkline data={m.trend.map((p) => p.value)} positive width={96} height={28} />
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {tab === "queue" && (
          !queueQ.data ? (
            <Skeleton className="h-64" />
          ) : (
            <div className="space-y-3">
              {queueQ.data.map((q, i) => {
                const statusStyle = {
                  completed: "text-positive",
                  processing: "text-primary",
                  pending: "text-muted-foreground",
                  failed: "text-negative",
                }[q.status]
                const barColor = {
                  completed: "bg-positive",
                  processing: "bg-primary",
                  pending: "bg-muted-foreground",
                  failed: "bg-negative",
                }[q.status]
                return (
                  <motion.div
                    key={q.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="rounded-lg border border-border bg-card p-4"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-foreground">
                          {q.ticker.slice(0, 3)}
                        </span>
                        <div>
                          <p className="font-mono font-semibold text-card-foreground">{q.ticker}</p>
                          <p className="text-xs text-muted-foreground">{q.requestedBy}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className={cn("text-xs font-semibold capitalize", statusStyle)}>{q.status}</span>
                        <p className="text-[10px] text-muted-foreground">{timeAgo(q.createdAt)}</p>
                      </div>
                    </div>
                    <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-accent">
                      <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${q.progress}%` }} />
                    </div>
                  </motion.div>
                )
              })}
            </div>
          )
        )}
      </div>
    </div>
  )
}
