"use client"

import { useState, useRef, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Sparkles, X, ArrowUp, Bot } from "lucide-react"
import { useT, useLangStore } from "@/lib/store"
import { MARKET_ASSETS } from "@/lib/data"

interface Msg {
  role: "user" | "assistant"
  text: string
}

const SUGGESTIONS = ["Forecast BTC", "Analyze AAPL", "Compare NVDA vs TSLA", "Show best signal today"]

import { api } from "@/lib/api"

export function AiCopilot() {
  const t = useT()
  const lang = useLangStore((s) => s.lang)
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMessages([
      {
        role: "assistant",
        text: lang === "vi"
          ? "Xin chào! Tôi là trợ lý AI của bạn. Bạn muốn tôi phân tích hoặc dự báo mã nào hôm nay?"
          : "Hello! I am your AI assistant. Which asset would you like me to analyze or forecast today?"
      }
    ])
  }, [lang])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, open])

  const send = async (text: string) => {
    const value = text.trim()
    if (!value) return
    
    // Format existing messages as history array
    const history = messages.map((m) => ({
      role: m.role,
      content: m.text,
    }))
    
    // Add user message immediately
    setMessages((m) => [...m, { role: "user", text: value }])
    setInput("")
    setIsLoading(true)
    
    try {
      const { reply, href } = await api.askCopilot(value, history, lang)
      setMessages((m) => [...m, { role: "assistant", text: reply }])
      if (href) setTimeout(() => router.push(href), 1000)
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: lang === "vi"
            ? "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại!"
            : "Sorry, an error occurred. Please try again!"
        }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <>
      <motion.button
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-50 flex h-13 w-13 items-center justify-center rounded-full bg-primary p-3.5 text-primary-foreground shadow-lg shadow-primary/20"
        aria-label={t("aiCopilot")}
      >
        {open ? <X className="h-6 w-6" /> : <Sparkles className="h-6 w-6" />}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-5 z-50 flex h-[28rem] w-[calc(100vw-2.5rem)] max-w-sm flex-col overflow-hidden rounded-xl border border-border bg-popover shadow-2xl"
          >
            <div className="flex items-center gap-2 border-b border-border bg-bg-secondary px-4 py-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
                <Bot className="h-4 w-4 text-primary-foreground" />
              </div>
              <div>
                <p className="text-sm font-semibold text-popover-foreground">{t("aiCopilot")}</p>
                <p className="text-[11px] text-positive">● Online</p>
              </div>
            </div>

            <div className="no-scrollbar flex-1 space-y-3 overflow-y-auto p-4">
              {messages.map((m, i) => (
                <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[80%] rounded-lg rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground"
                        : "max-w-[85%] rounded-lg rounded-bl-sm bg-accent px-3 py-2 text-sm text-accent-foreground"
                    }
                  >
                    {m.text}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-lg rounded-bl-sm bg-accent px-3 py-2 text-sm text-accent-foreground italic flex gap-1 items-center">
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            <div className="flex flex-wrap gap-1.5 border-t border-border px-3 py-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border bg-secondary px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                send(input)
              }}
              className="flex items-center gap-2 border-t border-border p-3"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={t("askAnything")}
                className="flex-1 rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/50"
              />
              <button
                type="submit"
                className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
                disabled={!input.trim() || isLoading}
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
