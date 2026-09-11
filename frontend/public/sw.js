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

// Tăng số này MỖI KHI thay asset tĩnh (icon, ảnh...). Service worker cache
// /icons/ nên nếu giữ nguyên version, trình duyệt của người đã từng vào site sẽ
// tiếp tục phục vụ icon CŨ từ cache và bản icon mới không bao giờ tới được họ.
// Dòng dọn cache ở sự kiện "activate" chỉ xoá các cache khác STATIC_CACHE hiện tại.
// v2: đồng bộ bộ icon PWA với favicon (src/app/icon.svg).
const CACHE_VERSION = "forecastai-v2"
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
      (async () => {
        try {
          const response = await fetch(event.request)
          // LỖI ĐÃ SỬA: service worker KHÔNG BAO GIỜ cache trang HTML (chỉ
          // isStaticAsset mới được cache), nên nhánh dự phòng bên dưới luôn trả
          // undefined và trình duyệt báo lỗi mạng. PWA "cài được" nhưng mở offline
          // vẫn trắng — trái hẳn mô tả ở đầu file. Nay lưu lại bản sao của trang
          // vừa tải thành công để còn có cái mà trả về khi mất mạng.
          if (response && response.ok) {
            const cache = await caches.open(STATIC_CACHE)
            cache.put(event.request, response.clone())
          }
          return response
        } catch (err) {
          const cache = await caches.open(STATIC_CACHE)
          const cached =
            (await cache.match(event.request)) || (await cache.match("/"))
          return cached || Response.error()
        }
      })(),
    )
  }
})
