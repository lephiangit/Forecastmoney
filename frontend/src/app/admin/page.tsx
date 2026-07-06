"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Bell, Users, UserCheck, DollarSign, Server, Activity, Cpu, ListChecks, Send } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { StatCard } from "@/components/ui/stat-card"
import { Sparkline } from "@/components/ui/sparkline"
import { Skeleton, ErrorCard } from "@/components/ui/states"
import { StatusDot, ConfidencePill } from "@/components/ui/tags"
import { formatCurrency, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

type Tab = "users" | "system" | "accuracy" | "queue" | "notifications"

export default function AdminPage() {
  const t = useT()
  const [tab, setTab] = useState<Tab>("users")
  const queryClient = useQueryClient()

  // Notification form state
  const [notifTitle, setNotifTitle] = useState("")
  const [notifMessage, setNotifMessage] = useState("")
  const [notifUserId, setNotifUserId] = useState("")
  const [isSending, setIsSending] = useState(false)

  const usersQ = useQuery({ queryKey: ["adminUsers"], queryFn: api.getAdminUsers })
  const systemQ = useQuery({ queryKey: ["systemMetrics"], queryFn: api.getSystemMetrics })
  const accuracyQ = useQuery({ queryKey: ["modelAccuracy"], queryFn: api.getModelAccuracy })
  const queueQ = useQuery({ queryKey: ["researchQueue"], queryFn: api.getResearchQueue })

  const users = Array.isArray(usersQ.data) ? usersQ.data : []
  const totalUsers = users.length
  const activeUsers = users.filter((u) => u?.status === "active").length
  const totalAum = users.reduce((s, u) => s + (Number(u?.portfolioValue) || 0), 0)

  const tabs: { value: Tab; label: string; icon: typeof Users }[] = [
    { value: "users", label: t("userManagement"), icon: Users },
    { value: "system", label: t("systemMonitoring"), icon: Server },
    { value: "accuracy", label: t("modelAccuracy"), icon: Cpu },
    { value: "queue", label: t("researchQueue"), icon: ListChecks },
    { value: "notifications", label: "Notifications", icon: Bell },
  ]

  const statusMut = useMutation({
    mutationFn: (id: string) => api.updateUserStatus(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["adminUsers"] })
  })

  const roleMut = useMutation({
    mutationFn: (id: string) => api.updateUserRole(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["adminUsers"] })
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["adminUsers"] })
  })

  const balanceMut = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) => api.updateUserBalance(id, amount),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["adminUsers"] })
  })

  const handleEditBalance = (id: string, currentBalance: number) => {
    const newBal = prompt("Enter new balance:", currentBalance.toString())
    if (newBal !== null) {
      const parsed = parseFloat(newBal)
      if (!isNaN(parsed)) {
        balanceMut.mutate({ id, amount: parsed })
      }
    }
  }

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Are you sure you want to permanently delete user ${name}?`)) {
      deleteMut.mutate(id)
    }
  }

  const isOnline = (lastActive?: string) => {
    if (!lastActive) return false
    const diff = new Date().getTime() - new Date(lastActive).getTime()
    return diff < 5 * 60 * 1000 // 5 minutes
  }

  return (
    <div>
      <PageHeader title={t("adminDashboard")} subtitle={t("howIsSystem")} />

      {/* KPI overview */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label={t("totalUsers")} value={totalUsers} format={(n) => (Number(n) || 0).toFixed(0)} icon={Users} accent />
        <StatCard label={t("activeUsers")} value={activeUsers} format={(n) => (Number(n) || 0).toFixed(0)} icon={UserCheck} delay={0.05} />
        <StatCard label={t("totalAum")} value={totalAum} format={(n) => formatCurrency(n, { compact: true })} icon={DollarSign} delay={0.1} />

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
                    <th className="px-4 py-3 font-medium">Online</th>
                    <th className="px-4 py-3 text-right font-medium">{t("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <motion.tr
                      key={u?.id || i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="border-b border-border/50 transition-colors hover:bg-muted/50"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground">
                            {String(u?.name || "U").slice(0, 2).toUpperCase()}
                          </span>
                          <div>
                            <p className="font-medium text-card-foreground">{u?.name || "Unknown User"}</p>
                            <p className="text-xs text-muted-foreground">{u?.email || ""}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "rounded px-2 py-0.5 text-xs font-semibold uppercase",
                          u?.role === "admin" ? "bg-primary/15 text-primary" : "bg-accent text-muted-foreground",
                        )}>
                          {u?.role || "USER"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2 text-xs capitalize text-card-foreground">
                          <StatusDot status={u?.status as any || "active"} /> {u?.status || "active"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-card-foreground">{formatCurrency(Number(u?.portfolioValue) || 0, { compact: true })}</td>
                      <td className="px-4 py-3 text-xs">
                        {isOnline(u?.lastActive) ? (
                          <span className="flex items-center gap-1.5 text-positive">
                            <span className="h-2 w-2 rounded-full bg-positive animate-pulse"></span>
                            Online
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{u?.lastActive ? timeAgo(u.lastActive) : "Never"}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleEditBalance(u?.id, Number(u?.portfolioValue) || 0)}
                            className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            Nạp tiền
                          </button>
                          <button
                            onClick={() => statusMut.mutate(u?.id)}
                            className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            {u?.status === "active" ? t("suspend") : t("activate")}
                          </button>
                          <button
                            onClick={() => roleMut.mutate(u?.id)}
                            className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            {u?.role === "admin" ? "Demote" : "Promote"}
                          </button>
                          <button
                            onClick={() => handleDelete(u?.id, u?.name)}
                            className="rounded-md border border-negative/30 px-2 py-1 text-xs font-medium text-negative hover:bg-negative/10"
                          >
                            Del
                          </button>
                        </div>
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
              {Array.isArray(systemQ.data) ? systemQ.data.map((m, i) => (
                <motion.div
                  key={m?.label || i}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-xl border border-border bg-card p-5"
                >
                  <p className="text-sm font-medium text-muted-foreground">{m?.label || "Unknown"}</p>
                  <p className="mt-2 font-mono text-2xl font-bold text-card-foreground">{m?.value || 0}</p>
                  <span className="mt-1 flex items-center gap-2 text-xs capitalize text-muted-foreground">
                    <StatusDot status={m?.status as any || "warning"} /> {m?.status || "warning"}
                  </span>
                </motion.div>
              )) : null}
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
                  {Array.isArray(accuracyQ.data) ? accuracyQ.data.map((m, i) => (
                    <motion.tr
                      key={m?.ticker || i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="border-b border-border/50 transition-colors hover:bg-muted/50"
                    >
                      <td className="px-4 py-3 font-medium text-card-foreground">{m?.model || "Unknown"}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-card-foreground">{m?.ticker || "Unknown"}</td>
                      <td className="px-4 py-3"><ConfidencePill value={Number(m?.accuracy) || 0} /></td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m?.mae || 0}</td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m?.rmse || 0}</td>
                      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{m?.predictions?.toLocaleString("en-US") || 0}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end">
                          <Sparkline data={Array.isArray(m?.trend) ? m.trend.map((p: any) => p?.value || 0) : []} positive width={96} height={28} />
                        </div>
                      </td>
                    </motion.tr>
                  )) : null}
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

        {tab === "notifications" && (
          <div className="rounded-lg border border-border bg-card p-6">
            <h3 className="text-lg font-bold text-card-foreground mb-4">Compose Notification</h3>
            <div className="space-y-4 max-w-2xl">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">Title</label>
                <input
                  type="text"
                  value={notifTitle}
                  onChange={(e) => setNotifTitle(e.target.value)}
                  placeholder="e.g. System Maintenance"
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">Message</label>
                <textarea
                  value={notifMessage}
                  onChange={(e) => setNotifMessage(e.target.value)}
                  placeholder="Enter notification content here..."
                  rows={4}
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">Target User ID (Optional)</label>
                <input
                  type="text"
                  value={notifUserId}
                  onChange={(e) => setNotifUserId(e.target.value)}
                  placeholder="Leave empty to broadcast to ALL users"
                  className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm outline-none focus:border-primary"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Global broadcasts will be seen by everyone. To target a specific user, enter their database ID.
                </p>
              </div>
              <button
                onClick={async () => {
                  if (!notifTitle || !notifMessage) return alert("Title and Message required.")
                  setIsSending(true)
                  try {
                    const uid = notifUserId.trim() ? parseInt(notifUserId.trim()) : null
                    const ok = await api.createNotification(notifTitle, notifMessage, uid)
                    if (ok) {
                      alert("Notification sent successfully!")
                      setNotifTitle("")
                      setNotifMessage("")
                      setNotifUserId("")
                    } else {
                      alert("Failed to send notification.")
                    }
                  } catch (e: any) {
                    alert("Error: " + e.message)
                  }
                  setIsSending(false)
                }}
                disabled={isSending || !notifTitle || !notifMessage}
                className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                <Send className="h-4 w-4" /> {isSending ? "Sending..." : "Send Notification"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
