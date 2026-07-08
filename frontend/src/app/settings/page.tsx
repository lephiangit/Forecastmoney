"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { User, Bell, Globe, Shield, Save, Check, LogOut, Lock, Loader2, X } from "lucide-react"
import { useAuthStore, useLangStore, useCurrencyStore, useT } from "@/lib/store"
import { api } from "@/lib/api"
import { PageHeader } from "@/components/ui/page-header"
import { cn } from "@/lib/utils"

export default function SettingsPage() {
  const t = useT()
  const { user, login, logout } = useAuthStore()
  const { lang, setLang } = useLangStore()
  const { currency, setCurrency } = useCurrencyStore()
  const [name, setName] = useState(user?.name ?? "")
  const [email, setEmail] = useState(user?.email ?? "")
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [notifs, setNotifs] = useState({ signals: true, trades: true, research: false, weekly: true })

  // Change password state
  const [showPwModal, setShowPwModal] = useState(false)
  const [oldPw, setOldPw] = useState("")
  const [newPw, setNewPw] = useState("")
  const [confirmPw, setConfirmPw] = useState("")
  const [pwLoading, setPwLoading] = useState(false)
  const [pwError, setPwError] = useState("")
  const [pwSuccess, setPwSuccess] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      // Update auth store with new name/email
      if (user) {
        if (typeof window !== "undefined") {
          localStorage.setItem(`forecastai-profile-${user.id}`, JSON.stringify({ name, email }));
        }
        login(name || user.name, user.role, user.id, email || user.email)
        // Also save to database
        try {
          await api.updateProfile(name || user.name)
        } catch (e) {
          console.error("Failed to save profile to DB", e)
        }
      }
      // Save notification preferences to localStorage
      if (typeof window !== "undefined") {
        localStorage.setItem("forecastai-notif-prefs", JSON.stringify(notifs))
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } finally {
      setSaving(false)
    }
  }

  async function handleChangePassword() {
    setPwError("")
    setPwSuccess(false)

    if (newPw.length < 4) {
      setPwError("Mật khẩu mới phải có ít nhất 4 ký tự")
      return
    }
    if (newPw !== confirmPw) {
      setPwError("Mật khẩu xác nhận không khớp")
      return
    }

    setPwLoading(true)
    try {
      await api.changePassword(oldPw, newPw)
      setPwSuccess(true)
      setOldPw("")
      setNewPw("")
      setConfirmPw("")
      setTimeout(() => {
        setShowPwModal(false)
        setPwSuccess(false)
      }, 2000)
    } catch (err: any) {
      setPwError(err.message || "Đổi mật khẩu thất bại")
    } finally {
      setPwLoading(false)
    }
  }

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

        {/* Currency */}
        <Section icon={Globe} title="Currency / Tiền tệ">
          <div className="flex gap-2">
            {(["USD", "VND"] as const).map((c) => (
              <button
                key={c}
                onClick={() => {
                  setCurrency(c)
                  window.location.reload()
                }}
                className={cn(
                  "rounded-md border px-4 py-2 text-sm font-semibold transition-colors",
                  currency === c
                    ? "border-primary/60 bg-primary/10 text-primary"
                    : "border-border bg-secondary text-muted-foreground hover:text-foreground",
                )}
              >
                {c === "USD" ? "USD ($)" : "VND (₫)"}
              </button>
            ))}
          </div>
        </Section>

        {/* Notifications */}
        <Section icon={Bell} title={t("notifications")}>
          <div className="space-y-1">
            <ToggleRow label={t("notifAiSignals")} value={notifs.signals} onChange={(v) => setNotifs((n) => ({ ...n, signals: v }))} />
            <ToggleRow label={t("notifAutoTrade")} value={notifs.trades} onChange={(v) => setNotifs((n) => ({ ...n, trades: v }))} />
            <ToggleRow label={t("notifResearch")} value={notifs.research} onChange={(v) => setNotifs((n) => ({ ...n, research: v }))} />
            <ToggleRow label={t("notifWeekly")} value={notifs.weekly} onChange={(v) => setNotifs((n) => ({ ...n, weekly: v }))} />
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground italic">
            {t("notifSavedLocally")}
          </p>
        </Section>

        {/* Security */}
        <Section icon={Shield} title={t("security")}>
          <div className="flex flex-wrap items-center gap-2">
            {user?.isOAuth !== true && (
              <button
                onClick={() => {
                  setShowPwModal(true)
                  setPwError("")
                  setPwSuccess(false)
                  setOldPw("")
                  setNewPw("")
                  setConfirmPw("")
                }}
                className="rounded-md border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
              >
                <Lock className="mr-1.5 inline h-3.5 w-3.5" />
                {t("changePassword")}
              </button>
            )}
            <button
              onClick={logout}
              className="inline-flex items-center gap-2 rounded-md border border-negative/30 bg-negative/10 px-4 py-2 text-sm font-medium text-negative transition-colors hover:bg-negative/20"
            >
              <LogOut className="h-4 w-4" /> {t("logout")}
            </button>
          </div>
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
            onClick={handleSave}
            disabled={saving}
            className={cn(
              "flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90",
              saving && "opacity-70",
            )}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {t("saveConfig")}
          </button>
        </div>
      </div>

      {/* Change Password Modal */}
      {showPwModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-card-foreground">Change Password</h3>
              <button
                onClick={() => setShowPwModal(false)}
                className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <FieldInput label="Current password" value={oldPw} onChange={setOldPw} type="password" />
              <FieldInput label="New password" value={newPw} onChange={setNewPw} type="password" />
              <FieldInput label="Confirm new password" value={confirmPw} onChange={setConfirmPw} type="password" />
            </div>

            {pwError && (
              <p className="mt-3 text-sm text-negative">{pwError}</p>
            )}
            {pwSuccess && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-3 flex items-center gap-1.5 text-sm text-positive"
              >
                <Check className="h-4 w-4" /> Đổi mật khẩu thành công!
              </motion.p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setShowPwModal(false)}
                className="rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                Cancel
              </button>
              <button
                onClick={handleChangePassword}
                disabled={pwLoading || pwSuccess}
                className={cn(
                  "flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90",
                  (pwLoading || pwSuccess) && "opacity-70",
                )}
              >
                {pwLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                {pwSuccess ? "Done" : "Change Password"}
              </button>
            </div>
          </motion.div>
        </div>
      )}
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
          "relative flex h-5 w-9 items-center rounded-full px-0.5 transition-colors",
          value ? "bg-primary" : "bg-accent",
        )}
        aria-label={label}
        role="switch"
        aria-checked={value}
      >
        <span
          className={cn(
            "h-4 w-4 rounded-full bg-background transition-transform",
            value ? "translate-x-4" : "translate-x-0",
          )}
        />
      </button>
    </div>
  )
}
