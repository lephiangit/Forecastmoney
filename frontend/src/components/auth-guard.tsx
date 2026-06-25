"use client"

import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import { useAuthStore } from "@/lib/store"
import { Loader2 } from "lucide-react"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user } = useAuthStore()
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    // If not logged in, wait a tiny bit to avoid flashing if state hydrates late
    const timer = setTimeout(() => {
      if (!useAuthStore.getState().user) {
        router.replace(`/login?returnUrl=${encodeURIComponent(pathname)}`)
      } else {
        setIsChecking(false)
      }
    }, 100)
    
    return () => clearTimeout(timer)
  }, [user, router, pathname])

  if (isChecking || !user) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return <>{children}</>
}
