"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState, useEffect } from "react"
import { Bell, Menu, X, ChevronDown, LogOut, Settings, Activity } from "lucide-react"
import { cn } from "@/lib/utils"
import { useLangStore, useT, useAuthStore } from "@/lib/store"
import type { TranslationKey } from "@/lib/i18n"
import { api } from "@/lib/api"
import type { Notification } from "@/lib/types"

const NAV: { href: string; key: TranslationKey; adminOnly?: boolean }[] = [
  { href: "/", key: "dashboard" },
  { href: "/markets", key: "markets" },
  { href: "/research", key: "research" },
  { href: "/forecast", key: "forecast" },
  { href: "/portfolio", key: "portfolio" },
  { href: "/auto-trade", key: "autoTrade" },
  { href: "/admin", key: "admin", adminOnly: true },
]

import { Trash2 } from "lucide-react"

function NotificationsMenu() {
  const { user } = useAuthStore()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  
  // Local storage for global notifications states
  const [localDeleted, setLocalDeleted] = useState<number[]>([])
  const [localRead, setLocalRead] = useState<number[]>([])

  useEffect(() => {
    if (typeof window !== "undefined") {
      const del = JSON.parse(localStorage.getItem("global_notifs_deleted") || "[]")
      const read = JSON.parse(localStorage.getItem("global_notifs_read") || "[]")
      setLocalDeleted(del)
      setLocalRead(read)
    }
  }, [])

  useEffect(() => {
    if (user) {
      const fetchNotifs = () => {
        api.getNotifications().then(data => {
          // Filter out locally deleted global notifications
          const visible = data.filter(n => !(n.user_id === null && localDeleted.includes(n.id)))
          setNotifications(visible)
        })
      }
      fetchNotifs()
      const interval = setInterval(fetchNotifs, 60000)
      return () => clearInterval(interval)
    }
  }, [user, localDeleted])

  const isNotifRead = (n: Notification) => {
    if (n.user_id === null) return localRead.includes(n.id)
    return n.is_read
  }

  const unreadCount = notifications.filter(n => !isNotifRead(n)).length

  async function markRead(n: Notification) {
    if (n.user_id === null) {
      const updated = [...localRead, n.id]
      setLocalRead(updated)
      localStorage.setItem("global_notifs_read", JSON.stringify(updated))
    } else {
      await api.markNotificationRead(n.id)
      setNotifications(prev => prev.map(p => p.id === n.id ? { ...p, is_read: true } : p))
    }
  }

  async function deleteNotif(n: Notification) {
    if (n.user_id === null) {
      const updated = [...localDeleted, n.id]
      setLocalDeleted(updated)
      localStorage.setItem("global_notifs_deleted", JSON.stringify(updated))
      setNotifications(prev => prev.filter(p => p.id !== n.id))
    } else {
      const ok = await api.deleteNotification(n.id)
      if (ok) {
        setNotifications(prev => prev.filter(p => p.id !== n.id))
      }
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Bell className="h-4.5 w-4.5" />
        {unreadCount > 0 && (
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-negative" />
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-lg border border-border bg-popover shadow-xl">
            <div className="border-b border-border px-4 py-3 font-semibold text-popover-foreground">
              Notifications
            </div>
            <div className="max-h-[300px] overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">No notifications</div>
              ) : (
                notifications.map(n => {
                  const read = isNotifRead(n)
                  return (
                    <div 
                      key={n.id} 
                      className={cn("border-b border-border p-4 transition-colors relative group", !read ? "bg-accent/50" : "bg-popover")}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-semibold text-popover-foreground">{n.title}</h4>
                        <div className="flex items-center gap-2">
                          {!read && (
                            <button 
                              onClick={() => markRead(n)}
                              className="text-xs text-primary hover:underline"
                            >
                              Mark read
                            </button>
                          )}
                          <button
                            onClick={() => deleteNotif(n)}
                            className="text-muted-foreground hover:text-negative opacity-0 transition-opacity group-hover:opacity-100"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{n.message}</p>
                      <p className="mt-2 text-[10px] text-muted-foreground/60">{new Date(n.created_at).toLocaleString()}</p>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function Logo() {
// ... UserMenu ...
// ... LangSwitch ...
  return (
    <Link href="/" className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
        <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
      </div>
      <span className="text-lg font-bold tracking-tight text-foreground">
        Forecast<span className="text-primary">AI</span>
      </span>
    </Link>
  )
}

function LangSwitch() {
  const { lang, toggleLang } = useLangStore()
  return (
    <button
      onClick={toggleLang}
      className="flex items-center gap-1 rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs font-semibold text-secondary-foreground transition-colors hover:bg-accent"
      aria-label="Toggle language"
    >
      <span className={cn(lang === "en" && "text-primary")}>EN</span>
      <span className="text-muted-foreground">/</span>
      <span className={cn(lang === "vi" && "text-primary")}>VI</span>
    </button>
  )
}

function UserMenu() {
  const t = useT()
  const { user, logout } = useAuthStore()
  const [open, setOpen] = useState(false)
  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Link
          href="/login"
          className="rounded-md px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent"
        >
          {t("login")}
        </Link>
        <Link
          href="/register"
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:opacity-90"
        >
          {t("register")}
        </Link>
      </div>
    )
  }
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-md border border-border bg-secondary py-1 pl-1 pr-2 transition-colors hover:bg-accent"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground">
          {user.name.slice(0, 2).toUpperCase()}
        </div>
        <span className="hidden text-sm font-medium text-foreground sm:inline">{user.name}</span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-popover shadow-xl">
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-popover-foreground">{user.name}</p>
              <p className="text-xs text-muted-foreground">{user.email}</p>
              <span className="mt-1 inline-block rounded bg-accent px-1.5 py-0.5 text-[10px] font-semibold uppercase text-muted-foreground">
                {user.role}
              </span>
            </div>
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2.5 text-sm text-popover-foreground transition-colors hover:bg-accent"
            >
              <Settings className="h-4 w-4" /> {t("settings")}
            </Link>
            <button
              onClick={() => {
                logout()
                setOpen(false)
              }}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-negative transition-colors hover:bg-accent"
            >
              <LogOut className="h-4 w-4" /> {t("logout")}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function Navbar() {
  const pathname = usePathname()
  const t = useT()
  const { user } = useAuthStore()
  const [mobileOpen, setMobileOpen] = useState(false)
  const items = NAV.filter((n) => !n.adminOnly || user?.role === "admin")

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href))

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4 lg:px-6">
        <div className="flex items-center gap-10">
          <Logo />
          <nav className="hidden items-center gap-1 lg:flex">
            {items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive(item.href)
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                )}
              >
                {t(item.key)}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <NotificationsMenu />
          <LangSwitch />
          <UserMenu />
          <button
            className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent lg:hidden"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label="Menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="border-t border-border bg-background px-4 py-2 lg:hidden">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "block rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                isActive(item.href) ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/60",
              )}
            >
              {t(item.key)}
            </Link>
          ))}
        </nav>
      )}
    </header>
  )
}
