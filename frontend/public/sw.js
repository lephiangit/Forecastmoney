/**
 * Service worker tối giản cho PWA ForecastAI.
 *
 * Mục tiêu: (1) cho phép "cài đặt" web như app thật (điều kiện bắt buộc của
 * PWA installability là phải có service worker đăng ký thành công), và
 * (2) cache các asset tĩnh (JS/CSS/icon) để lần mở sau nhanh hơn và app-shell
 * còn hiển thị được cả khi mất mạng tạm thời.
 *
 * KHÔNG cache dữ liệu động (API /market, /forecast...) — dữ liệu tài chính
 * cũ mà hiển thị như đang "sống" là nguy hiểm hơn nhiều so với việc chậm một
 * chút. Chiến lược: network-first cho API + trang HTML, cache-first cho asset
 * tĩnh có hash trong tên file (bất biến, an toàn để cache dài hạn).
 */

const CACHE_VERSION = "forecastai-v1"
const STATIC_CACHE = `${CACHE_VERSION}-static`

self.addEventListener("install", (event) => {
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("forecastai-") && key !== STATIC_CACHE)
          .map((key) => caches.delete(key)),
      ),
    ),
  )
  self.clients.claim()
})

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    /\.(png|jpg|jpeg|svg|webp|ico|woff2?)$/.test(url.pathname)
  )
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url)

  // Chỉ can thiệp request GET cùng origin — bỏ qua API backend (thường ở
  // origin khác trên Render) và mọi request POST/PUT/DELETE.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return
  }

  if (isStaticAsset(url)) {
    // Cache-first: asset tĩnh của Next.js có hash trong tên nên không lo cũ.
    event.respondWith(
      caches.open(STATIC_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request)
        if (cached) return cached
        try {
          const response = await fetch(event.request)
          if (response.ok) cache.put(event.request, response.clone())
          return response
        } catch (err) {
          return cached || Response.error()
        }
      }),
    )
    return
  }

  // Trang HTML: network-first, chỉ rơi về cache khi mất mạng hoàn toàn —
  // để không bao giờ hiển thị giao diện cũ khi đang có mạng bình thường.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.open(STATIC_CACHE).then((cache) => cache.match(event.request)),
      ),
    )
  }
})
