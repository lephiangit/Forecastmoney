"use client"

/**
 * states.tsx – Các trạng thái giao diện dùng chung: loading, rỗng, lỗi.
 *
 * Mở rộng so với bản trước (chỉ có Skeleton, ErrorCard, EmptyState):
 *
 *   - Skeleton có hiệu ứng vệt sáng chạy, và có các biến thể sẵn cho
 *     bảng / thẻ số liệu / biểu đồ, để mỗi trang không phải tự dựng lại khung chờ.
 *   - ErrorCard hiển thị được thông điệp cụ thể thay vì luôn một câu chung chung.
 *   - Thêm InlineSpinner và LoadingOverlay cho các thao tác trong trang.
 *   - Mọi trạng thái đều có thuộc tính ARIA phù hợp, để trình đọc màn hình
 *     thông báo được rằng nội dung đang tải hoặc vừa có lỗi.
 */

import type { CSSProperties, ReactNode } from "react"
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT, useLangStore } from "@/lib/store"

/* ══════════════════════════════════════════════════════════════════════════
   SKELETON
   ══════════════════════════════════════════════════════════════════════════ */

export function Skeleton({
  className,
  style,
}: {
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      aria-hidden
      style={style}
      className={cn("shimmer rounded-md bg-accent/50", className)}
    />
  )
}

/** Khung chờ cho một hàng thẻ số liệu. */
export function StatCardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div
      role="status"
      aria-label="Đang tải số liệu"
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="fa-card p-4">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-3 h-7 w-28" />
          <Skeleton className="mt-2 h-3 w-16" />
        </div>
      ))}
    </div>
  )
}

/** Khung chờ cho một bảng dữ liệu. */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div role="status" aria-label="Đang tải bảng dữ liệu" className="fa-card overflow-hidden">
      <div className="flex gap-4 border-b border-border px-4 py-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 border-b border-border/50 px-4 py-3.5 last:border-0">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={cn("h-4 flex-1", c === 0 && "max-w-24")} />
          ))}
        </div>
      ))}
    </div>
  )
}

/** Khung chờ cho một biểu đồ. */
export function ChartSkeleton({ height = 320 }: { height?: number }) {
  return (
    <div
      role="status"
      aria-label="Đang tải biểu đồ"
      className="fa-card flex flex-col justify-end gap-2 p-4"
      style={{ height }}
    >
      <div className="flex flex-1 items-end gap-1.5">
        {/* Chiều cao cố định theo mẫu lặp, không dùng Math.random():
            giá trị ngẫu nhiên khiến kết quả render ở server và client khác nhau,
            gây lỗi hydration mismatch trong Next.js. */}
        {[45, 62, 38, 71, 55, 83, 49, 66, 41, 77, 58, 69, 44, 73, 52].map((h, i) => (
          <Skeleton key={i} className="flex-1" style={{ height: `${h}%` }} />
        ))}
      </div>
      <div className="flex justify-between pt-2">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════════════════
   LỖI
   ══════════════════════════════════════════════════════════════════════════ */

export function ErrorCard({
  onRetry,
  title,
  message,
  className,
}: {
  onRetry?: () => void
  title?: string
  message?: string
  className?: string
}) {
  const t = useT()

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/25 bg-destructive/5 p-8 text-center",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/15">
        <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden />
      </div>
      <div className="max-w-md">
        <p className="font-semibold text-card-foreground">{title ?? t("errorTitle")}</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {message ?? t("errorBody")}
        </p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-2 rounded-md border border-border bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          {t("retry")}
        </button>
      )}
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════════════════
   RỖNG
   ══════════════════════════════════════════════════════════════════════════ */

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: {
  title: string
  description?: string
  icon?: typeof AlertTriangle
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-card/40 p-10 text-center",
        className,
      )}
    >
      <Icon className="h-8 w-8 text-muted-foreground" aria-hidden />
      <p className="mt-1 font-medium text-card-foreground">{title}</p>
      {description && (
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════════════════
   ĐANG XỬ LÝ
   ══════════════════════════════════════════════════════════════════════════ */

export function InlineSpinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-hidden />
}

/**
 * Lớp phủ mờ khi một thao tác đang chạy (ví dụ: bấm "Chạy dự báo").
 * Nội dung cũ vẫn hiện mờ phía dưới, giúp người dùng không mất ngữ cảnh.
 */
export function LoadingOverlay({ label }: { label?: string }) {
  const lang = useLangStore((s) => s.lang)
  const defaultLabel = lang === "en" ? "Processing…" : "Đang xử lý…"

  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-lg bg-background/70 backdrop-blur-sm"
    >
      <InlineSpinner className="h-6 w-6 text-primary" />
      <p className="text-sm text-muted-foreground">{label ?? defaultLabel}</p>
    </div>
  )
}

/**
 * Thông báo tiến trình dài — ví dụ khi đang chờ backend trên gói free thức dậy.
 * Nói rõ vì sao phải chờ sẽ dễ chịu hơn nhiều so với một vòng xoay im lặng.
 */
export function SlowLoadingNotice({ className }: { className?: string }) {
  const lang = useLangStore((s) => s.lang)
  const text =
    lang === "en"
      ? "First request may take 30-60 seconds while the free-tier server wakes up."
      : "Lần gọi đầu tiên có thể mất 30-60 giây vì máy chủ (gói miễn phí) đang khởi động lại."

  return (
    <p className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <InlineSpinner className="h-3 w-3" />
      {text}
    </p>
  )
}
