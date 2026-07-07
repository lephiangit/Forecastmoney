"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Activity, Mail, Lock, Eye, EyeOff, Loader2, X } from "lucide-react"
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

export default function LoginPage() {
  const t = useT()
  const router = useRouter()
  const { login } = useAuthStore()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  // Forgot password state
  const [showForgot, setShowForgot] = useState(false)
  const [forgotEmail, setForgotEmail] = useState("")
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotSuccess, setForgotSuccess] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await api.login(email, password)
      if (res.token) {
        localStorage.setItem("forecast_ai_token", res.token)
        login(res.username, res.role || "user", res.user_id?.toString())
        
        // Handle returnUrl if exists
        const params = new URLSearchParams(window.location.search)
        const returnUrl = params.get("returnUrl")
        router.push(returnUrl || "/")
      }
    } catch (err: any) {
      alert(err.message || "Failed to login")
    } finally {
      setLoading(false)
    }
  }

  async function submitForgot(e: React.FormEvent) {
    e.preventDefault()
    if (!forgotEmail) return
    setForgotLoading(true)
    try {
      await api.forgotPassword(forgotEmail)
      setForgotSuccess(true)
    } catch (err: any) {
      alert(err.message || "Failed to send reset email")
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="absolute inset-0 -z-10 opacity-[0.04] [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:40px_40px]" />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md relative"
      >
        <Link href="/" className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary">
            <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">
            Forecast<span className="text-primary">AI</span>
          </span>
        </Link>

        <div className="rounded-xl border border-border bg-card p-6 shadow-xl sm:p-8">
          <h1 className="text-xl font-bold text-card-foreground">{t("welcomeBack")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("howIsMyAccount")}</p>

          <button
            type="button"
            onClick={async () => {
              try {
                await signInWithGoogle();
              } catch (err: any) {
                alert(err.message || "Failed to initiate Google login");
              }
            }}
            className="mt-6 flex w-full items-center justify-center gap-2.5 rounded-md border border-border bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-accent"
          >
            <GoogleIcon className="h-4.5 w-4.5" />
            Continue with Google
          </button>

          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-wide text-muted-foreground">or</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field
              label={t("email")}
              icon={Mail}
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
            />
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
                  autoComplete="current-password"
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

            <div className="flex items-center justify-end text-xs">
              <button
                type="button"
                onClick={() => {
                  setForgotEmail(email)
                  setShowForgot(true)
                  setForgotSuccess(false)
                }}
                className="font-medium text-primary hover:underline"
              >
                Forgot password?
              </button>
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
              {t("login")}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            {t("noAccount")}{" "}
            <Link href="/register" className="font-semibold text-primary hover:underline">
              {t("register")}
            </Link>
          </p>
        </div>

        {/* Forgot Password Modal */}
        <AnimatePresence>
          {showForgot && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 z-50 flex items-center justify-center rounded-xl bg-background/80 backdrop-blur-sm"
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="w-full rounded-xl border border-border bg-card p-6 shadow-2xl"
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-card-foreground">Reset Password</h2>
                  <button onClick={() => setShowForgot(false)} className="text-muted-foreground hover:text-foreground">
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {forgotSuccess ? (
                  <div className="text-center py-4">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-positive/20 text-positive">
                      <Mail className="h-6 w-6" />
                    </div>
                    <p className="text-sm font-medium text-foreground">Check your email</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      We've sent a password reset link to <br/>
                      <span className="font-semibold">{forgotEmail}</span>
                    </p>
                    <button
                      onClick={() => setShowForgot(false)}
                      className="mt-6 w-full rounded-md border border-border bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground hover:bg-accent"
                    >
                      Close
                    </button>
                  </div>
                ) : (
                  <form onSubmit={submitForgot} className="space-y-4">
                    <p className="text-xs text-muted-foreground mb-2">
                      Enter your email address and we'll send you a link to reset your password.
                    </p>
                    <Field
                      label="Email Address"
                      icon={Mail}
                      type="email"
                      value={forgotEmail}
                      onChange={setForgotEmail}
                      placeholder="you@example.com"
                    />
                    <button
                      type="submit"
                      disabled={forgotLoading || !forgotEmail}
                      className={cn(
                        "flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90",
                        (forgotLoading || !forgotEmail) && "opacity-70",
                      )}
                    >
                      {forgotLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                      Send Reset Link
                    </button>
                  </form>
                )}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

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
          autoComplete={type === "email" ? "username" : (type === "password" ? "current-password" : "off")}
          className="w-full rounded-md border border-border bg-secondary py-2.5 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/60"
        />
      </div>
    </div>
  )
}
