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
