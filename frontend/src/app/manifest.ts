import type { MetadataRoute } from "next"

/**
 * Next.js quy ước file: `app/manifest.ts` tự sinh ra `/manifest.webmanifest`
 * và tự chèn thẻ <link rel="manifest"> — không cần viết tay file JSON tĩnh
 * lẫn thẻ <link> trong layout.tsx.
 *
 * PWA cho phép cài đặt ForecastAI như một app thật trên điện thoại lẫn PC
 * (Android Chrome: "Cài đặt ứng dụng"; iOS Safari: "Thêm vào MH chính";
 * Windows/macOS Chrome/Edge: icon cài đặt trên thanh địa chỉ).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ForecastAI — Phân tích thị trường bằng AI",
    short_name: "ForecastAI",
    description:
      "Dự báo giá bằng Temporal Fusion Transformer kết hợp phân tích tin tức bằng LLM. Giao dịch mô phỏng, không phải lời khuyên đầu tư.",
    start_url: "/",
    display: "standalone",
    // Khớp với --background của theme tối mặc định (globals.css) — tránh
    // nháy trắng giữa splash screen và lúc trang thật render xong.
    background_color: "#0b0e11",
    theme_color: "#0b0e11",
    orientation: "portrait-primary",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  }
}
