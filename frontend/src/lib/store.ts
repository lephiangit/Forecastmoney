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
}

interface AuthState {
  user: AuthUser | null
  login: (name: string, role?: Role, id?: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      login: (name, role = "user", id) =>
        set({
          user: {
            id: id || name,
            name: name,
            email: name,
            role,
          },
        }),
      logout: () => {
        if (typeof window !== "undefined") localStorage.removeItem("forecast_ai_token")
        set({ user: null })
      },
    }),
    { name: "forecastai-auth" },
  ),
)
