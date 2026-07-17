"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuthStore } from "@/lib/store"
import { AuthGuard } from "@/components/auth-guard"
import { Loader2 } from "lucide-react"

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user } = useAuthStore()
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      const currentUser = useAuthStore.getState().user
      if (currentUser && currentUser.role !== "admin") {
        router.replace("/")
      } else {
        setIsChecking(false)
      }
    }, 100)
    return () => clearTimeout(timer)
  }, [user, router])

  if (isChecking || (user && user.role !== "admin")) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return <AuthGuard>{children}</AuthGuard>
}
