"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Activity, Lock, Eye, EyeOff, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import { supabase } from "@/lib/supabase"
import { cn } from "@/lib/utils"

export default function ResetPasswordPage() {
  const router = useRouter()
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [verifying, setVerifying] = useState(true)
  
  const [sessionData, setSessionData] = useState<{ email: string; token: string } | null>(null)

  useEffect(() => {
    async function checkSession() {
      try {
        // Supabase client automatically picks up the #access_token from URL
        const { data: { session }, error } = await supabase.auth.getSession()
        
        if (error || !session || !session.user.email) {
          throw new Error("Invalid or expired reset link")
        }
        
        setSessionData({
          email: session.user.email,
          token: session.access_token
        })
      } catch (err: any) {
        alert(err.message || "Invalid or expired reset link. Please request a new one.")
        router.push("/login")
      } finally {
        setVerifying(false)
      }
    }
    
    checkSession()
  }, [router])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!sessionData) return
    
    if (password.length < 4) {
      alert("Password must be at least 4 characters long")
      return
    }
    
    if (password !== confirmPassword) {
      alert("Passwords do not match")
      return
    }
    
    setLoading(true)
    try {
      await api.resetPassword(sessionData.email, password, sessionData.token)
      alert("Password reset successfully. You can now login.")
      router.push("/login")
    } catch (err: any) {
      alert(err.message || "Failed to reset password")
    } finally {
      setLoading(false)
    }
  }

  if (verifying) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="absolute inset-0 -z-10 opacity-[0.04] [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:40px_40px]" />
      
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <div className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary">
            <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">
            Forecast<span className="text-primary">AI</span>
          </span>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-xl sm:p-8">
          <h1 className="text-xl font-bold text-card-foreground">Set New Password</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Please enter your new password for <span className="font-semibold text-foreground">{sessionData?.email}</span>.
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">New Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
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
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Confirm New Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type={showPw ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-md border border-border bg-secondary py-2.5 pl-9 pr-10 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/60"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !password || !confirmPassword}
              className={cn(
                "mt-2 flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90",
                (loading || !password || !confirmPassword) && "opacity-70",
              )}
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              Reset Password
            </button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
