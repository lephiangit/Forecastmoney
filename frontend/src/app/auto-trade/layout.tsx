import { AuthGuard } from "@/components/auth-guard"

export default function AutoTradeLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>
}
