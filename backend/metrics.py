"""
metrics.py – Thu thập số liệu vận hành THẬT của tiến trình.

Bản trước của trang Admin hiển thị số liệu sinh bằng `random.uniform(...)`:
độ trễ API, thời gian inference, số kết nối DB, tỷ lệ lỗi đều là số bịa.
Với một đồ án, việc dashboard hiển thị số liệu giả là điểm trừ nặng khi bảo vệ —
nên module này đo số liệu thật, chấp nhận đo được ít chỉ số hơn.

Toàn bộ state nằm trong RAM tiến trình và reset khi service khởi động lại.
Đó là đánh đổi có chủ ý: đủ dùng cho một web service đơn lẻ, không cần thêm hạ tầng.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, List

# Số mẫu độ trễ giữ lại để tính trung vị / p95.
_MAX_SAMPLES = 500


class _Metrics:
    def __init__(self) -> None:
        self.started_at = time.time()
        self._lock = threading.Lock()

        self.request_latencies: Deque[float] = deque(maxlen=_MAX_SAMPLES)
        self.inference_latencies: Deque[float] = deque(maxlen=_MAX_SAMPLES)

        self.total_requests = 0
        self.error_requests = 0  # số response có status >= 500

        # Đếm theo từng nguồn phân tích để biết Groq có đang bị rate-limit không.
        self.research_source_counts: Dict[str, int] = {}

    # ── Ghi nhận ──────────────────────────────────────────────────────────────

    def record_request(self, duration_ms: float, status_code: int) -> None:
        with self._lock:
            self.request_latencies.append(duration_ms)
            self.total_requests += 1
            if status_code >= 500:
                self.error_requests += 1

    def record_inference(self, duration_ms: float) -> None:
        with self._lock:
            self.inference_latencies.append(duration_ms)

    def record_research_source(self, source: str) -> None:
        with self._lock:
            self.research_source_counts[source] = self.research_source_counts.get(source, 0) + 1

    # ── Truy vấn ──────────────────────────────────────────────────────────────

    @staticmethod
    def _percentile(values: List[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = min(int(len(ordered) * pct), len(ordered) - 1)
        return ordered[idx]

    def snapshot(self) -> dict:
        with self._lock:
            latencies = list(self.request_latencies)
            inferences = list(self.inference_latencies)
            total = self.total_requests
            errors = self.error_requests
            sources = dict(self.research_source_counts)

        uptime_seconds = time.time() - self.started_at

        return {
            "uptime_seconds": round(uptime_seconds),
            "uptime_human": _format_duration(uptime_seconds),
            "total_requests": total,
            "error_requests": errors,
            "error_rate_pct": round(errors / total * 100, 2) if total else 0.0,
            "api_latency_p50_ms": round(self._percentile(latencies, 0.50), 1),
            "api_latency_p95_ms": round(self._percentile(latencies, 0.95), 1),
            "inference_p50_ms": round(self._percentile(inferences, 0.50), 1),
            "inference_p95_ms": round(self._percentile(inferences, 0.95), 1),
            "inference_samples": len(inferences),
            "research_sources": sources,
        }


def _format_duration(seconds: float) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}n {hours}g"
    if hours:
        return f"{hours}g {minutes}p"
    return f"{minutes}p"


metrics = _Metrics()


class track_inference:
    """
    Context manager đo thời gian một lượt inference.

        with track_inference():
            model.predict(...)
    """

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        metrics.record_inference((time.perf_counter() - self._start) * 1000)
        return False
