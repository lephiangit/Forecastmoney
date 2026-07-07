"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Activity } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { api } from "@/lib/api"
import { useAuthStore } from "@/lib/store"

export default function AuthCallbackPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [status, setStatus] = useState("Đang xác thực...")
  const [detail, setDetail] = useState("")

  useEffect(() => {
    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout>

    async function exchangeForCustomJWT(session: any) {
      if (cancelled) return
      try {
        setStatus("Đang đồng bộ tài khoản...")
        // Send Supabase token to our backend to get a custom JWT
        const res = await api.loginWithGoogle(session.access_token)
        if (cancelled) return

        if (res.token) {
          // Store the CUSTOM JWT (not the Supabase token)
          localStorage.setItem("forecast_ai_token", res.token)
          login(res.username, res.role || "user", res.user_id?.toString())
          setStatus("Đăng nhập thành công! Đang chuyển hướng...")
          router.push("/")
        } else {
          throw new Error("No token returned from backend")
        }
      } catch (err: any) {
        if (cancelled) return
        setStatus("Lỗi đăng nhập Google")
        setDetail(err.message || "Could not authenticate with backend")
        setTimeout(() => router.push("/login?error=google_auth_failed"), 3000)
      }
    }

    async function handleCallback() {
      try {
        const hash = window.location.hash
        const search = window.location.search

        // Step 1: Try getSession immediately (Supabase may have already parsed the URL)
        const { data: { session }, error } = await supabase.auth.getSession()

        if (error) {
          setStatus(`Lỗi: ${error.message}`)
          setDetail(JSON.stringify(error))
          setTimeout(() => router.push("/login?error=session_error"), 3000)
          return
        }

        if (session) {
          await exchangeForCustomJWT(session)
          return
        }

        // Step 2: If no session yet, listen for SIGNED_IN event
        setStatus("Đang chờ xác thực từ Google...")
        const { data: listener } = supabase.auth.onAuthStateChange(async (event, currentSession) => {
          if (cancelled) return
          if ((event === "SIGNED_IN" || event === "TOKEN_REFRESHED") && currentSession) {
            cancelled = true
            if (timeoutId) clearTimeout(timeoutId)
            await exchangeForCustomJWT(currentSession)
          }
        })

        // Step 3: Fallback - try PKCE code exchange if there's a ?code= param
        const code = new URLSearchParams(window.location.search).get("code")
        if (code) {
          setStatus("Đang trao đổi mã xác thực...")
          const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
          if (!exchangeError && data.session) {
            cancelled = true
            if (timeoutId) clearTimeout(timeoutId)
            await exchangeForCustomJWT(data.session)
            return
          }
          if (exchangeError) {
            setDetail(`Code exchange error: ${exchangeError.message}`)
          }
        }

        // Timeout after 10 seconds
        timeoutId = setTimeout(() => {
          if (!cancelled) {
            listener.subscription.unsubscribe()
            setStatus("Hết thời gian chờ. Đang chuyển về trang đăng nhập...")
            setDetail("Không nhận được phiên đăng nhập từ Google. Vui lòng thử lại.")
            setTimeout(() => router.push("/login?error=auth_timeout"), 2000)
          }
        }, 10000)

      } catch (err: any) {
        setStatus(`Lỗi: ${err?.message || "Unknown"}`)
        setDetail(String(err))
        setTimeout(() => router.push("/login?error=callback_error"), 3000)
      }
    }

    handleCallback()

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [router, login])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-md bg-primary animate-pulse mb-4">
        <Activity className="h-6 w-6 text-primary-foreground" strokeWidth={2.5} />
      </div>
      <h2 className="text-xl font-bold mb-2">{status}</h2>
      <p className="text-muted-foreground mb-4">Vui lòng đợi trong giây lát.</p>

      {detail && (
        <div className="mt-4 p-3 bg-muted text-left text-xs font-mono rounded max-w-md break-words">
          <p className="text-muted-foreground">{detail}</p>
        </div>
      )}
    </div>
  )
}
