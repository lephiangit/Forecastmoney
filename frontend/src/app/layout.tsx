import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'

import './globals.css'
import { AppShell } from '@/components/layout/app-shell'
import { Providers } from '@/components/providers'

// Giữ subset 'latin' như bản gốc. Không thêm 'vietnamese': không phải font nào
// trên Google Fonts cũng có subset đó, và next/font sẽ làm hỏng build nếu thiếu.
// Dấu tiếng Việt vẫn hiển thị đúng qua font dự phòng của hệ thống.
const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'ForecastAI — Phân tích thị trường bằng AI',
    template: '%s · ForecastAI',
  },
  // Mô tả cũ ghi "Gemini research" trong khi hệ thống dùng Groq (Llama 3.3).
  // Ghi sai công nghệ trong metadata là chi tiết dễ bị soi khi chấm đồ án.
  description:
    'Đồ án học thuật: dự báo giá bằng Temporal Fusion Transformer kết hợp phân tích tin tức bằng LLM. Giao dịch mô phỏng, không phải lời khuyên đầu tư.',
  applicationName: 'ForecastAI',
  // Trang có nội dung tài chính do AI sinh ra và giao dịch mô phỏng —
  // không nên xuất hiện trong kết quả tìm kiếm như một dịch vụ tài chính thật.
  robots: { index: false, follow: false },
  // manifest tự sinh bởi app/manifest.ts (quy ước file của Next.js) — không
  // cần khai báo lại icons ở đây cho phần PWA, chỉ cần apple-touch-icon vì
  // iOS Safari không đọc "icons" trong Web App Manifest.
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'ForecastAI',
  },
  icons: {
    apple: '/icons/icon-192.png',
  },
}

export const viewport: Viewport = {
  // 'dark light': trang hỗ trợ cả hai theme (người dùng tự chọn qua nút trên
  // navbar), không chỉ dark như bản gốc.
  colorScheme: 'dark light',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f8fafc' },
    { media: '(prefers-color-scheme: dark)', color: '#0b0e11' },
  ],
  width: 'device-width',
  initialScale: 1,
  // Không đặt maximumScale: chặn người dùng phóng to là rào cản
  // với người khiếm thị một phần, và vi phạm WCAG 1.4.4.
}

/**
 * Chống nháy (FOUC) khi đổi theme: chạy TRƯỚC khi React hydrate, đọc thẳng
 * localStorage (không đợi zustand khởi tạo) để gắn class "light" lên <html>
 * kịp lúc trình duyệt vẽ khung hình đầu tiên.
 *
 * Nếu chưa từng lưu lựa chọn nào (raw rỗng), tạm thời không thêm class gì cả
 * — mặc định dark của :root đã khớp với đa số người dùng mới; ThemeSync
 * (components/providers.tsx) sẽ dò prefers-color-scheme ngay sau khi hydrate
 * xong và cập nhật lại nếu hệ thống người dùng đang ở chế độ sáng.
 */
const THEME_ANTI_FLICKER_SCRIPT = `
(function () {
  try {
    var raw = localStorage.getItem('forecastai-theme');
    if (!raw) return;
    var parsed = JSON.parse(raw);
    var theme = parsed && parsed.state && parsed.state.theme;
    if (theme === 'light') document.documentElement.classList.add('light');
  } catch (e) {}
})();
`

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    // lang khớp với giá trị mặc định của useLangStore ("en"). Người dùng đổi
    // ngôn ngữ ở phía client; giữ nguyên ở đây để trình đọc màn hình không bị
    // lệch giữa lần render đầu trên server và trạng thái sau khi hydrate.
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} bg-background`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_ANTI_FLICKER_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
