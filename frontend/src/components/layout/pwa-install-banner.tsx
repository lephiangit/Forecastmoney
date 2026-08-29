"use client"

import { useEffect, useState } from "react"
import { Download, X } from "lucide-react"
import { useT } from "@/lib/store"

const DISMISS_KEY = "forecastai-pwa-dismissed-at"
// Nếu người dùng đóng banner, không hỏi lại trong 14 ngày — hỏi mỗi lần mở
// trang là kiểu UX gây khó chịu nhất của các web có PWA.
const DISMISS_SNOOZE_MS = 14 * 24 * 60 * 60 * 1000

/**
 * Banner gợi ý "cài đặt ForecastAI như một ứng dụng".
 *
 * Chrome/Edge (Android, Windows, macOS) bắn sự kiện `beforeinstallprompt` khi
 * trang đạt đủ điều kiện installability (có manifest hợp lệ + service worker
 * đăng ký thành công + phục vụ qua HTTPS). Ta chặn sự kiện mặc định của trình
 * duyệt (thường là icon nhỏ trên thanh địa chỉ, dễ bị bỏ sót) và tự hiển thị
 * banner rõ ràng hơn.
 *
 * Safari (iOS/macOS) KHÔNG bắn sự kiện này — cài đặt qua "Chia sẻ → Thêm vào
 * màn hình chính" thủ công, nên banner này sẽ không tự hiện trên Safari.
 */
export function PwaInstallBanner() {
  const t = useT()
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault()

      try {
        const dismissedAt = Number(localStorage.getItem(DISMISS_KEY) || 0)
        if (Date.now() - dismissedAt < DISMISS_SNOOZE_MS) return
      } catch {
        // localStorage bị chặn — vẫn hiện banner, chỉ là không nhớ lựa chọn cũ.
      }

      setDeferredPrompt(e)
      setVisible(true)
    }

    window.addEventListener("beforeinstallprompt", handler)
    // App đã được cài rồi thì không cần hỏi lại nữa.
    window.addEventListener("appinstalled", () => setVisible(false))

    return () => window.removeEventListener("beforeinstallprompt", handler)
  }, [])

  const handleInstall = async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    await deferredPrompt.userChoice
    setDeferredPrompt(null)
    setVisible(false)
  }

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()))
    } catch {
      // Không lưu được cũng không sao — chỉ là banner có thể hiện lại sớm hơn.
    }
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed inset-x-4 bottom-4 z-40 flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-lg sm:inset-x-auto sm:right-4 sm:w-96">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Download className="h-4.5 w-4.5" />
        </div>
        <div>
          <p className="text-sm font-medium text-card-foreground">{t("pwaInstallTitle")}</p>
          <p className="text-xs text-muted-foreground">{t("pwaInstallDesc")}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <button
          onClick={handleInstall}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
        >
          {t("pwaInstallCta")}
        </button>
        <button
          onClick={handleDismiss}
          aria-label={t("dismiss")}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
