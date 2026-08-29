"use client"

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { ArrowRight, LineChart, ShieldAlert, Sparkles, TrendingUp, X } from "lucide-react"
import { useT } from "@/lib/store"

const SEEN_KEY = "forecastai-onboarding-seen-v1"

/**
 * Tour giới thiệu cho người dùng mới, hiện một lần duy nhất (đánh dấu qua
 * localStorage). Mục đích: người không rành tài chính vẫn hiểu được các khái
 * niệm cốt lõi trước khi nhìn vào một trang đầy số liệu — độ tin cậy, chỉ báo
 * kỹ thuật, và quan trọng nhất là bản chất "mô phỏng, không phải lời khuyên
 * đầu tư thật" của toàn bộ sản phẩm.
 *
 * Không hiện lại nếu người dùng đã thấy — không có nút "xem lại" để giữ đơn
 * giản; localStorage.removeItem(SEEN_KEY) trong console là cách duy nhất để
 * xem lại thủ công (chấp nhận được vì đây là tour giới thiệu, không phải tài
 * liệu tham khảo).
 */
export function OnboardingTour() {
  const t = useT()
  const [step, setStep] = useState(0)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    try {
      if (!localStorage.getItem(SEEN_KEY)) setVisible(true)
    } catch {
      // localStorage bị chặn — bỏ qua tour thay vì hiện lại mỗi lần tải trang.
    }
  }, [])

  const steps = [
    {
      icon: Sparkles,
      title: t("onboardStep1Title"),
      body: t("onboardStep1Body"),
    },
    {
      icon: TrendingUp,
      title: t("onboardStep2Title"),
      body: t("onboardStep2Body"),
    },
    {
      icon: LineChart,
      title: t("onboardStep3Title"),
      body: t("onboardStep3Body"),
    },
    {
      icon: ShieldAlert,
      title: t("onboardStep4Title"),
      body: t("onboardStep4Body"),
    },
  ]

  const close = () => {
    try {
      localStorage.setItem(SEEN_KEY, "1")
    } catch {
      // Không lưu được thì tour có thể hiện lại lần sau — chấp nhận được.
    }
    setVisible(false)
  }

  const next = () => {
    if (step < steps.length - 1) setStep(step + 1)
    else close()
  }

  if (!visible) return null

  const current = steps[step]
  const Icon = current.icon
  const isLast = step === steps.length - 1

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
      >
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.98 }}
          className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary/15 text-primary">
              <Icon className="h-5 w-5" />
            </div>
            <button
              onClick={close}
              aria-label={t("dismiss")}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <h2 id="onboarding-title" className="text-lg font-semibold text-card-foreground">
            {current.title}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{current.body}</p>

          <div className="mt-6 flex items-center justify-between">
            <div className="flex gap-1.5">
              {steps.map((_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === step ? "w-6 bg-primary" : "w-1.5 bg-border"
                  }`}
                />
              ))}
            </div>
            <button
              onClick={next}
              className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {isLast ? t("onboardFinish") : t("onboardNext")}
              {!isLast && <ArrowRight className="h-3.5 w-3.5" />}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
