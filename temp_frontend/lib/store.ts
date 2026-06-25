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
  login: (email: string, role?: Role) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: {
        id: "u_1",
        name: "Alex Chen",
        email: "alex@forecastai.io",
        role: "admin",
      },
      login: (email, role = "user") =>
        set({
          user: {
            id: "u_1",
            name: email.split("@")[0] || "Trader",
            email,
            role,
          },
        }),
      logout: () => set({ user: null }),
    }),
    { name: "forecastai-auth" },
  ),
)
