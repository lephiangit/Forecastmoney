"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Activity } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/store"

export default function AuthCallbackPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [status, setStatus] = useState("Đang xác thực...")
  const [detail, setDetail] = useState("")

  useEffect(() => {
    let cancelled = false

    async function handleCallback() {
      try {
        const url = new URL(window.location.href)
        const code = url.searchParams.get("code")
        const errorParam = url.searchParams.get("error")
        const errorDesc = url.searchParams.get("error_description")

        setDetail(`URL params: code=${code ? "yes" : "no"}, error=${errorParam || "none"}`)

        // If Supabase/Google returned an error
        if (errorParam) {
          setStatus(`Lỗi: ${errorDesc || errorParam}`)
          setTimeout(() => router.push("/login?error=oauth_error"), 3000)
          return
        }

        // PKCE flow: exchange the code for a session
        if (code) {
          setStatus("Đang trao đổi mã xác thực...")
          const { data, error } = await supabase.auth.exchangeCodeForSession(code)
          
          if (error) {
            setStatus(`Lỗi trao đổi mã: ${error.message}`)
            setDetail(JSON.stringify(error))
            setTimeout(() => router.push("/login?error=code_exchange"), 3000)
            return
          }

          if (data.session) {
            processSession(data.session)
            return
          }
        }

        // Fallback: try getSession (for implicit flow or already-authenticated)
        setStatus("Đang kiểm tra phiên đăng nhập...")
        const { data: { session } } = await supabase.auth.getSession()
        
        if (session) {
          processSession(session)
          return
        }

        // Last resort: listen for auth state change
        setStatus("Đang chờ xác thực từ Google...")
        const { data: listener } = supabase.auth.onAuthStateChange((event, currentSession) => {
          if (cancelled) return
          setDetail(`Event: ${event}`)
          if (event === "SIGNED_IN" && currentSession) {
            processSession(currentSession)
          }
        })

        // Timeout after 8 seconds
        setTimeout(() => {
          if (!cancelled) {
            listener.subscription.unsubscribe()
            setStatus("Hết thời gian chờ. Đang chuyển về trang đăng nhập...")
            setTimeout(() => router.push("/login?error=auth_timeout"), 2000)
          }
        }, 8000)

      } catch (err: any) {
        setStatus(`Lỗi: ${err?.message || "Unknown"}`)
        setTimeout(() => router.push("/login?error=callback_error"), 3000)
      }
    }

    function processSession(session: any) {
      if (cancelled) return
      cancelled = true
      setStatus("Đăng nhập thành công! Đang chuyển hướng...")
      
      // Store the access token for backend API calls
      localStorage.setItem("forecast_ai_token", session.access_token)
      
      const user = session.user
      const name = user.user_metadata?.full_name || user.email || "Trader"
      login(name, "user", user.id)
      
      router.push("/")
    }

    handleCallback()

    return () => { cancelled = true }
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
