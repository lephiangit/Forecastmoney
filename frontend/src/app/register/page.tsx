"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Activity, Mail, Lock, User, Eye, EyeOff, Loader2, Check } from "lucide-react"
import { api } from "@/lib/api"
import { useAuthStore, useT } from "@/lib/store"
import { cn } from "@/lib/utils"
import { signInWithGoogle } from "@/lib/supabase"

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.47 14.97.5 12 .5A11 11 0 0 0 2.18 6.94L5.84 9.9C6.71 7.3 9.14 4.75 12 4.75Z"
      />
    </svg>
  )
}

const BENEFITS = [
  "Real-time AI price forecasts (TFT-v3)",
  "Gemini-powered research reports",
  "Automated paper-trading bot",
]

export default function RegisterPage() {
  const t = useT()
  const router = useRouter()
  const { login } = useAuthStore()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await api.register(email, password)
      if (res.token) {
        localStorage.setItem("forecast_ai_token", res.token)
        login(res.username, res.role || "user")
        router.push("/")
      }
    } catch (err: any) {
      alert(err.message || "Failed to register")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="absolute inset-0 -z-10 opacity-[0.04] [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:40px_40px]" />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="grid w-full max-w-4xl overflow-hidden rounded-xl border border-border bg-card shadow-xl lg:grid-cols-2"
      >
        <div className="hidden flex-col justify-between bg-secondary/50 p-8 lg:flex">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary">
              <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <span className="text-xl font-bold tracking-tight text-foreground">
              Forecast<span className="text-primary">AI</span>
            </span>
          </Link>
          <div>
            <h2 className="text-2xl font-bold text-foreground text-balance">
              Trade smarter with AI on your side.
            </h2>
            <ul className="mt-6 space-y-3">
              {BENEFITS.map((b) => (
                <li key={b} className="flex items-center gap-3 text-sm text-muted-foreground">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-positive/15 text-positive">
                    <Check className="h-3 w-3" />
                  </span>
                  {b}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-muted-foreground">Paper trading only. No real funds involved.</p>
        </div>

        <div className="p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
              <Activity className="h-4.5 w-4.5 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <span className="text-lg font-bold tracking-tight text-foreground">
              Forecast<span className="text-primary">AI</span>
            </span>
          </div>

          <h1 className="text-xl font-bold text-card-foreground">{t("createAccount")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("whatIsHappening")}</p>

          <button
            type="button"
            onClick={async () => {
              try {
                await signInWithGoogle();
              } catch (err: any) {
                alert(err.message || "Failed to initiate Google signup");
              }
            }}
            className="mt-6 flex w-full items-center justify-center gap-2.5 rounded-md border border-border bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-accent"
          >
            <GoogleIcon className="h-4.5 w-4.5" />
            Sign up with Google
          </button>

          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-wide text-muted-foreground">or</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field label={t("name")} icon={User} type="text" value={name} onChange={setName} placeholder="Jane Trader" />
            <Field label={t("email")} icon={Mail} type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-muted-foreground">{t("password")}</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="password"
                  name="password"
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-md border border-border bg-secondary py-2.5 pl-9 pr-10 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/60"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={showPw ? "Hide password" : "Show password"}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90",
                loading && "opacity-70",
              )}
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {t("register")}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            {t("haveAccount")}{" "}
            <Link href="/login" className="font-semibold text-primary hover:underline">
              {t("login")}
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}

function Field({
  label,
  icon: Icon,
  type,
  value,
  onChange,
  placeholder,
}: {
  label: string
  icon: typeof Mail
  type: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const id = label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</label>
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          id={id}
          name={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-md border border-border bg-secondary py-2.5 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/60"
        />
      </div>
    </div>
  )
}
