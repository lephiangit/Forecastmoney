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

/**
 * Đăng ký service worker (public/sw.js) — điều kiện bắt buộc để trang được
 * trình duyệt coi là "installable" (cài được như app trên điện thoại/PC).
 * Chỉ chạy phía client, sau khi trang đã load xong để không cạnh tranh
 * băng thông với các request quan trọng hơn lúc tải trang lần đầu.
 */
function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return

    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Đăng ký thất bại (ví dụ chạy trên http không phải localhost) —
        // không phải lỗi nghiêm trọng, trang vẫn hoạt động bình thường,
        // chỉ là không cài đặt được như app.
      })
    }

    if (document.readyState === "complete") register()
    else window.addEventListener("load", register)

    return () => window.removeEventListener("load", register)
  }, [])

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
      <ServiceWorkerRegister />
      {children}
    </QueryClientProvider>
  )
}
