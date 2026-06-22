import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ForecastAI — Crypto & Market Intelligence",
  description: "AI-powered financial market research and price forecasting platform combining news sentiment with technical analysis",
  keywords: ["crypto forecast", "AI trading", "market analysis", "TFT forecast", "sentiment analysis"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className="dark">
      <body className={`${inter.variable} font-sans bg-[#0b0e11] text-[#eaecef] antialiased`}>
        {children}
      </body>
    </html>
  );
}
