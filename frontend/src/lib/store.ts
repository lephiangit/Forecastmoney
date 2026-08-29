"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { Lang, TranslationKey } from "./i18n"
import { translations } from "./i18n"

interface LangState {
  lang: Lang
  setLang: (lang: Lang) => void
  toggleLang: () => void
}

export const useLangStore = create<LangState>()(
  persist(
    (set) => ({
      lang: "en",
      setLang: (lang) => set({ lang }),
      toggleLang: () => set((s) => ({ lang: s.lang === "en" ? "vi" : "en" })),
    }),
    { name: "forecastai-lang" },
  ),
)

export type Theme = "dark" | "light"

interface ThemeState {
  theme: Theme
  /** true sau khi đã có một lựa chọn tường minh (người dùng bấm nút, hoặc đã
   *  dò prefers-color-scheme lần đầu) — phân biệt với giá trị mặc định "dark"
   *  lúc chưa hydrate, để không dò lại prefers-color-scheme mỗi lần tải trang. */
  resolved: boolean
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  markResolved: () => void
}

/**
 * Giá trị mặc định phải khớp với CSS mặc định (:root, không có class "light")
 * để không có khoảng lệch giữa lần render đầu trên server và trước khi
 * script chống nháy trong <head> kịp chạy (xem app/layout.tsx).
 */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "dark",
      resolved: false,
      setTheme: (theme) => set({ theme, resolved: true }),
      toggleTheme: () => set((s) => ({ theme: s.theme === "dark" ? "light" : "dark", resolved: true })),
      markResolved: () => set({ resolved: true }),
    }),
    { name: "forecastai-theme" },
  ),
)

export type GlobalCurrency = "USD" | "VND"

interface CurrencyState {
  currency: GlobalCurrency
  exchangeRate: number
  lastFetched: number
  setCurrency: (currency: GlobalCurrency) => void
  setExchangeRate: (rate: number) => void
  toggleCurrency: () => void
}

export const useCurrencyStore = create<CurrencyState>()(
  persist(
    (set) => ({
      currency: "USD",
      exchangeRate: 25400,
      lastFetched: 0,
      setCurrency: (currency) => set({ currency }),
      setExchangeRate: (rate) => set({ exchangeRate: rate, lastFetched: Date.now() }),
      toggleCurrency: () => set((s) => ({ currency: s.currency === "USD" ? "VND" : "USD" })),
    }),
    { name: "forecastai-currency" },
  ),
)

export function useT() {
  const lang = useLangStore((s) => s.lang)
  return (key: TranslationKey) => translations[lang][key] ?? key
}

export type Role = "user" | "admin"

interface AuthUser {
  id: string
  name: string
  email: string
  role: Role
  isOAuth: boolean
}

interface AuthState {
  user: AuthUser | null
  login: (name: string, role?: Role, id?: string, email?: string, isOAuth?: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      login: (name, role = "user", id, email, isOAuth = false) => {
        let finalName = name;
        let finalEmail = email || name;
        if (typeof window !== "undefined") {
          try {
            const saved = localStorage.getItem(`forecastai-profile-${id || name}`);
            if (saved) {
              const parsed = JSON.parse(saved);
              if (parsed.name) finalName = parsed.name;
              if (parsed.email) finalEmail = parsed.email;
            }
          } catch (e) {}
        }
        set({
          user: {
            id: id || name,
            name: finalName,
            email: finalEmail,
            role,
            isOAuth,
          },
        })
      },
      logout: () => {
        if (typeof window !== "undefined") localStorage.removeItem("forecast_ai_token")
        set({ user: null })
      },
    }),
    { name: "forecastai-auth" },
  ),
)
