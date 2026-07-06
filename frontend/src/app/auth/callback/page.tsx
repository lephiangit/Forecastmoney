"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Activity, Loader2 } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/store"

export default function AuthCallbackPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [debugLog, setDebugLog] = useState("Starting auth...")
  const [debugLog2, setDebugLog2] = useState("")

  useEffect(() => {
    let timeoutId: NodeJS.Timeout
    let subscription: any

    function processSession(session: any) {
      if (timeoutId) clearTimeout(timeoutId)
      localStorage.setItem("forecast_ai_token", session.access_token)
      const user = session.user
      const name = user.user_metadata?.full_name || user.email || "Trader"
      login(name, "user", user.id)
      router.push("/")
    }

    async function handleCallback() {
      try {
        setDebugLog2("URL: " + window.location.href)
        // Try to get session immediately
        const { data: { session }, error } = await supabase.auth.getSession()
        
        if (session) {
          setDebugLog("Session found immediately! Redirecting...")
          processSession(session)
          return
        }

        setDebugLog("No session immediately, waiting for SIGNED_IN event...")
        // If no session yet, wait for the SIGNED_IN event
        const { data } = supabase.auth.onAuthStateChange((event, currentSession) => {
          setDebugLog(`Event received: ${event}`)
          if (event === 'SIGNED_IN' && currentSession) {
            processSession(currentSession)
          }
        })
        subscription = data.subscription

        // Fallback: if after 5 seconds still no session
        timeoutId = setTimeout(() => {
          setDebugLog("Timeout! No session after 5 seconds.")
          setTimeout(() => router.push("/login?error=auth_timeout"), 3000)
        }, 5000)

      } catch (err: any) {
        setDebugLog(`Error: ${err?.message || "Unknown error"}`)
      }
    }

    handleCallback()

    return () => {
      if (timeoutId) clearTimeout(timeoutId)
      if (subscription) subscription.unsubscribe()
    }
  }, [router, login])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-md bg-primary animate-pulse mb-4">
        <Activity className="h-6 w-6 text-primary-foreground" strokeWidth={2.5} />
      </div>
      <h2 className="text-xl font-bold mb-2">Đang xác thực tài khoản...</h2>
      <p className="text-muted-foreground mb-4">Vui lòng đợi trong giây lát.</p>
      
      {/* Debug Info */}
      <div className="mt-8 p-4 bg-muted text-left text-xs font-mono rounded overflow-hidden max-w-full break-words">
        <p className="font-bold text-red-500 mb-2">DEBUG INFO (Chụp ảnh màn hình này gửi cho DEV):</p>
        <p>{debugLog}</p>
        <p className="mt-2 text-blue-400">{debugLog2}</p>
      </div>
    </div>
  )
}

