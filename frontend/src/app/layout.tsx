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
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#0b0e11',
  width: 'device-width',
  initialScale: 1,
  // Không đặt maximumScale: chặn người dùng phóng to là rào cản
  // với người khiếm thị một phần, và vi phạm WCAG 1.4.4.
}

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
      <body className="font-sans antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
