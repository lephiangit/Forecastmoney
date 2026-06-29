"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { Activity, Loader2 } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/lib/store"

export default function AuthCallbackPage() {
  const router = useRouter()
  const { login } = useAuthStore()

  useEffect(() => {
    async function handleCallback() {
      try {
        const { data: { session }, error } = await supabase.auth.getSession()
        
        if (error) {
          throw error
        }

        if (session) {
          // Store the Supabase JWT token. Our backend `get_current_user` 
          // knows how to verify both custom JWTs and Supabase JWTs.
          localStorage.setItem("forecast_ai_token", session.access_token)
          
          const user = session.user
          const name = user.user_metadata?.full_name || user.email || "Trader"
          
          login(name, "user", user.id)
          
          // Redirect to dashboard
          router.push("/")
        } else {
          // If no session, they shouldn't be here
          router.push("/login")
        }
      } catch (err) {
        console.error("Auth callback error:", err)
        router.push("/login?error=auth_failed")
      }
    }

    handleCallback()
  }, [router, login])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="absolute inset-0 -z-10 opacity-[0.04] [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:40px_40px]" />
      
      <div className="flex flex-col items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-md bg-primary animate-pulse">
          <Activity className="h-6 w-6 text-primary-foreground" strokeWidth={2.5} />
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <p>Authenticating...</p>
        </div>
      </div>
    </div>
  )
}
