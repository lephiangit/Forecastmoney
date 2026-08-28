"use client"

/**
 * use-backend-status.ts – Theo dõi trạng thái kết nối tới backend.
 *
 * VẤN ĐỀ CẦN GIẢI QUYẾT
 *
 * `lib/api.ts` bắt mọi lỗi mạng và âm thầm trả về dữ liệu mẫu trong `lib/data.ts`.
 * Thiết kế này đúng ở chỗ giao diện không bị vỡ khi backend ngủ (Render free tier
 * cho service ngủ sau 15 phút không có traffic) — nhưng nó tạo ra một vấn đề
 * nghiêm trọng hơn: người dùng KHÔNG CÓ CÁCH NÀO phân biệt số liệu thật với
 * số liệu mẫu. Trong một ứng dụng tài chính, đó là điều không chấp nhận được;
 * khi demo đồ án, việc trình bày dữ liệu mẫu như dữ liệu thật còn tệ hơn nữa.
 *
 * CÁCH TIẾP CẬN
 *
 * Thay vì gắn thiết bị đo vào từng lời gọi API, ta thăm dò `/health` theo chu kỳ.
 * Một điểm kiểm tra duy nhất, không đụng vào luồng dữ liệu đang chạy, và trả lời
 * đúng câu hỏi mà người dùng quan tâm: "những gì tôi đang xem có phải số liệu
 * thật không?"
 */

import { useEffect } from "react"
import { create } from "zustand"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL

/** Khoảng thời gian giữa hai lần thăm dò khi backend đang khoẻ. */
const POLL_INTERVAL_OK = 60_000
/** Thăm dò dày hơn khi mất kết nối, để phát hiện lúc backend tỉnh lại. */
const POLL_INTERVAL_DOWN = 15_000
/**
 * Render free tier mất 30-60 giây để đánh thức service đang ngủ, nên timeout
 * phải đủ rộng — nếu không, ta sẽ báo "offline" trong khi thực ra chỉ đang chờ.
 */
const HEALTH_TIMEOUT = 8_000

export type BackendStatus = "checking" | "online" | "offline" | "not-configured"

interface BackendHealth {
  status: BackendStatus
  dbConnected: boolean | null
  llmConfigured: boolean | null
  tftLoaded: boolean | null
  lastChecked: number | null
  setHealth: (partial: Partial<Omit<BackendHealth, "setHealth">>) => void
}

export const useBackendStore = create<BackendHealth>((set) => ({
  status: BASE_URL ? "checking" : "not-configured",
  dbConnected: null,
  llmConfigured: null,
  tftLoaded: null,
  lastChecked: null,
  setHealth: (partial) => set(partial),
}))

/**
 * Gắn vòng thăm dò. Chỉ gọi MỘT LẦN ở gốc ứng dụng (AppShell) —
 * gọi ở nhiều nơi sẽ tạo ra nhiều vòng lặp trùng nhau.
 */
export function useBackendStatusPolling() {
  const setHealth = useBackendStore((s) => s.setHealth)

  useEffect(() => {
    if (!BASE_URL) {
      setHealth({ status: "not-configured", lastChecked: Date.now() })
      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function probe() {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT)

      try {
        const res = await fetch(`${BASE_URL}/health`, {
          signal: controller.signal,
          cache: "no-store",
        })
        clearTimeout(timeout)

        if (cancelled) return

        if (res.ok) {
          const data = await res.json()
          setHealth({
            status: "online",
            dbConnected: data.db_connected ?? null,
            llmConfigured: data.llm_configured ?? null,
            tftLoaded: data.tft_loaded ?? null,
            lastChecked: Date.now(),
          })
        } else {
          setHealth({ status: "offline", lastChecked: Date.now() })
        }
      } catch {
        clearTimeout(timeout)
        if (!cancelled) setHealth({ status: "offline", lastChecked: Date.now() })
      }

      if (cancelled) return

      const nextDelay =
        useBackendStore.getState().status === "online" ? POLL_INTERVAL_OK : POLL_INTERVAL_DOWN
      timer = setTimeout(probe, nextDelay)
    }

    probe()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [setHealth])
}

/**
 * Tiện ích cho từng trang: `true` khi số liệu đang hiển thị nhiều khả năng
 * là dữ liệu mẫu chứ không phải dữ liệu thật từ backend.
 */
export function useIsDemoData(): boolean {
  const status = useBackendStore((s) => s.status)
  return status === "offline" || status === "not-configured"
}
