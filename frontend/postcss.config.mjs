// Tailwind CSS v4 chạy như một plugin PostCSS. THIẾU FILE NÀY THÌ BUILD HỎNG.
//
// Vì sao: `src/app/globals.css` mở đầu bằng `@import 'tailwindcss'` và
// `@import 'tw-animate-css'`. Khi không có cấu hình PostCSS, Turbopack tự phân
// giải hai lệnh @import đó bằng resolver CSS của chính nó — resolver này KHÔNG
// áp dụng điều kiện export "style" của package.
//
//   - `tailwindcss` có thêm điều kiện "import"/"require" nên vẫn phân giải được,
//     nhưng lại ra file JS — nên KHÔNG có utility class nào được sinh ra.
//   - `tw-animate-css` chỉ khai báo duy nhất `{".": {"style": "./dist/tw-animate.css"}}`
//     nên không phân giải được gì cả:
//         Module not found: Can't resolve 'tw-animate-css'
//     → `next build` thất bại hoàn toàn.
//
// Với plugin @tailwindcss/postcss, chính Tailwind xử lý các lệnh @import này
// bằng resolver riêng (có honor điều kiện "style"), rồi biên dịch ra CSS thật.
// Đã đo: có file này → build ra ~60KB CSS đầy đủ utility; không có → build lỗi.
const config = {
  plugins: ['@tailwindcss/postcss'],
}

export default config
