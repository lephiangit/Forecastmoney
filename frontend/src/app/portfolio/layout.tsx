import { AuthGuard } from "@/components/auth-guard"

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>
}
