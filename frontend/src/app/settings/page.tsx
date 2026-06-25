"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { User, Bell, Globe, Shield, Save, Check, LogOut } from "lucide-react"
import { useAuthStore, useLangStore, useT } from "@/lib/store"
import { PageHeader } from "@/components/ui/page-header"
import { cn } from "@/lib/utils"

export default function SettingsPage() {
  const t = useT()
  const { user, logout } = useAuthStore()
  const { lang, setLang } = useLangStore()
  const [name, setName] = useState(user?.name ?? "")
  const [email, setEmail] = useState(user?.email ?? "")
  const [saved, setSaved] = useState(false)
  const [notifs, setNotifs] = useState({ signals: true, trades: true, research: false, weekly: true })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={t("settings")} subtitle={t("howIsMyAccount")} />

      <div className="space-y-6">
        {/* Profile */}
        <Section icon={User} title="Profile">
          <div className="grid gap-4 sm:grid-cols-2">
            <FieldInput label={t("name")} value={name} onChange={setName} />
            <FieldInput label={t("email")} value={email} onChange={setEmail} type="email" />
          </div>
          <div className="mt-4 flex items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">{t("role")}:</span>
            <span className="rounded bg-accent px-2 py-0.5 text-xs font-semibold uppercase text-foreground">
              {user?.role ?? "user"}
            </span>
          </div>
        </Section>

        {/* Language */}
        <Section icon={Globe} title="Language / Ngôn ngữ">
          <div className="flex gap-2">
            {(["en", "vi"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={cn(
                  "rounded-md border px-4 py-2 text-sm font-semibold transition-colors",
                  lang === l
                    ? "border-primary/60 bg-primary/10 text-primary"
                    : "border-border bg-secondary text-muted-foreground hover:text-foreground",
                )}
              >
                {l === "en" ? "English" : "Tiếng Việt"}
              </button>
            ))}
          </div>
        </Section>

        {/* Notifications */}
        <Section icon={Bell} title="Notifications">
          <div className="space-y-1">
            <ToggleRow label="AI signal alerts" value={notifs.signals} onChange={(v) => setNotifs((n) => ({ ...n, signals: v }))} />
            <ToggleRow label="Auto-trade executions" value={notifs.trades} onChange={(v) => setNotifs((n) => ({ ...n, trades: v }))} />
            <ToggleRow label="New research reports" value={notifs.research} onChange={(v) => setNotifs((n) => ({ ...n, research: v }))} />
            <ToggleRow label="Weekly performance summary" value={notifs.weekly} onChange={(v) => setNotifs((n) => ({ ...n, weekly: v }))} />
          </div>
        </Section>

        {/* Security */}
        <Section icon={Shield} title="Security">
          <button className="rounded-md border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent">
            Change password
          </button>
          <button
            onClick={logout}
            className="ml-2 inline-flex items-center gap-2 rounded-md border border-negative/30 bg-negative/10 px-4 py-2 text-sm font-medium text-negative transition-colors hover:bg-negative/20"
          >
            <LogOut className="h-4 w-4" /> {t("logout")}
          </button>
        </Section>

        <div className="flex items-center justify-end gap-3">
          {saved && (
            <motion.span
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-1.5 text-sm text-positive"
            >
              <Check className="h-4 w-4" /> Saved
            </motion.span>
          )}
          <button
            onClick={() => setSaved(true)}
            className="flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Save className="h-4 w-4" /> {t("saveConfig")}
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ icon: Icon, title, children }: { icon: typeof User; title: string; children: React.ReactNode }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-border bg-card p-5"
    >
      <h2 className="mb-4 flex items-center gap-2 font-semibold text-card-foreground">
        <Icon className="h-4 w-4 text-primary" /> {title}
      </h2>
      {children}
    </motion.section>
  )
}

function FieldInput({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-secondary px-3 py-2.5 text-sm text-foreground outline-none focus:border-primary/60"
      />
    </div>
  )
}

function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-sm text-card-foreground">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors",
          value ? "bg-primary" : "bg-accent",
        )}
        aria-label={label}
        role="switch"
        aria-checked={value}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-background transition-transform",
            value ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  )
}
