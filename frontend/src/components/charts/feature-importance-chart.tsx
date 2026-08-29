"use client"

import { useQuery } from "@tanstack/react-query"
import { Info } from "lucide-react"
import { api } from "@/lib/api"
import { useT } from "@/lib/store"
import { Skeleton } from "@/components/ui/states"

interface FeatureImportanceChartProps {
  ticker: string
}

/**
 * Hiển thị permutation importance cho dự báo T+1.
 *
 * ĐÍNH CHÍNH quan trọng (xem thêm backend/models/forecaster.py,
 * compute_feature_importance()): con số ở đây KHÔNG phải trọng số của lớp
 * VariableSelectionNetwork trong tft_model.py — lớp đó tồn tại trong code
 * nhưng chưa từng được model thật sự gọi tới. Thay vào đó đây là permutation
 * importance: xáo trộn từng đặc trưng trong 60 phiên gần nhất và đo dự báo
 * lệch bao nhiêu — một kỹ thuật diễn giải chuẩn, đo được trên chính model
 * đang chạy, không cần sửa kiến trúc hay train lại.
 */
export function FeatureImportanceChart({ ticker }: FeatureImportanceChartProps) {
  const t = useT()
  const { data, isLoading, isError } = useQuery({
    queryKey: ["feature-importance", ticker],
    queryFn: () => api.getFeatureImportance(ticker),
    staleTime: 6 * 60 * 60 * 1000, // khớp thời hạn cache 6h của forecast/combined
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-full" />
        ))}
      </div>
    )
  }

  if (isError || !data || data.length === 0) {
    return null
  }

  const top = data.slice(0, 8)
  const maxImportance = Math.max(...top.map((f) => f.importance), 0.0001)

  return (
    <div>
      <div className="space-y-2.5">
        {top.map((f) => (
          <div key={f.feature} className="flex items-center gap-3">
            <span className="w-20 shrink-0 truncate font-mono text-xs text-muted-foreground" title={f.feature}>
              {f.feature}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.max(4, (f.importance / maxImportance) * 100)}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums text-card-foreground">
              {(f.importance * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {t("featureImportanceNote")}
      </p>
    </div>
  )
}
