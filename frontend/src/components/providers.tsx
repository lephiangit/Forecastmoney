"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useEffect, useState, type ReactNode } from "react"

import { useThemeStore } from "@/lib/store"

/**
 * Đồng bộ class "light" trên <html> với useThemeStore.
 *
 * Script chống nháy trong app/layout.tsx đã đặt đúng class này TRƯỚC khi React
 * hydrate (đọc thẳng localStorage, không đợi zustand). Component này lo phần
 * còn lại của vòng đời: (1) lần đầu tiên CHƯA TỪNG lưu lựa chọn nào — dò
 * prefers-color-scheme một lần duy nhất; (2) mọi lần theme đổi sau đó do
 * người dùng bấm nút — cập nhật lại class ngay, không cần tải lại trang.
 */
function ThemeSync() {
  const theme = useThemeStore((s) => s.theme)
  const setTheme = useThemeStore((s) => s.setTheme)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy một lần lúc mount
    try {
      const raw = window.localStorage.getItem("forecastai-theme")
      if (!raw) {
        const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches
        setTheme(prefersLight ? "light" : "dark")
      }
    } catch {
      // localStorage có thể bị chặn (chế độ riêng tư nghiêm ngặt) — mặc định dark vẫn ổn.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle("light", theme === "light")
  }, [theme])

  return null
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 20_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  )
  return (
    <QueryClientProvider client={client}>
      <ThemeSync />
      {children}
    </QueryClientProvider>
  )
}
