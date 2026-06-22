"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { researchApi, type ResearchAnalysis } from "@/lib/api";
import { ArrowLeft, RefreshCw, TrendingUp, TrendingDown, AlertTriangle, ExternalLink, Clock, Newspaper } from "lucide-react";

function cn(...c: (string | false | undefined)[]) { return c.filter(Boolean).join(" "); }

function SentimentGauge({ score }: { score: number }) {
  const pct = ((score + 1) / 2) * 100;
  const color = score > 0.2 ? "#0ecb81" : score < -0.2 ? "#f6465d" : "#fcd535";
  return (
    <div className="mt-4">
      <div className="flex justify-between text-[12px] text-[#707a8a] mb-1 font-semibold">
        <span>Tiêu cực -1.0</span>
        <span className="font-mono" style={{ color }}>{score.toFixed(2)}</span>
        <span>Tích cực +1.0</span>
      </div>
      <div className="h-2 bg-[#2b3139] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, #f6465d, #fcd535, #0ecb81)` }}
        />
      </div>
      <div className="relative" style={{ paddingLeft: `${pct}%` }}>
        <div className="w-1 h-3 rounded-full mt-0.5" style={{ background: color }} />
      </div>
    </div>
  );
}

export default function ResearchPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const upperTicker = ticker.toUpperCase();

  const [analysis, setAnalysis] = useState<ResearchAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(force = false) {
    setLoading(true); setError(null);
    try {
      const res = await researchApi.analyze(upperTicker, force);
      setAnalysis(res);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message);
      else setError("Lỗi kết nối");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [upperTicker]); // eslint-disable-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect

  const sentCfg = {
    BULLISH: { label: "Tích cực (Bullish)", icon: <TrendingUp size={24} />, color: "#0ecb81", bg: "from-[#0ecb81]/10 to-transparent" },
    BEARISH: { label: "Tiêu cực (Bearish)", icon: <TrendingDown size={24} />, color: "#f6465d", bg: "from-[#f6465d]/10 to-transparent" },
    NEUTRAL: { label: "Trung tính (Neutral)", icon: <AlertTriangle size={24} />, color: "#fcd535", bg: "from-[#fcd535]/10 to-transparent" },
  }[analysis?.sentiment || "NEUTRAL"] || { label: "N/A", icon: null, color: "#707a8a", bg: "from-transparent to-transparent" };

  return (
    <div className="min-h-screen bg-[#0b0e11]">
      <nav className="navbar-sticky sticky top-0 z-50 border-b border-[#2b3139]">
        <div className="max-w-5xl mx-auto px-4 h-[64px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-[#707a8a] hover:text-[#ffffff] transition-colors"><ArrowLeft size={20} /></Link>
            <span className="font-bold text-[#fcd535] text-[20px] tracking-[-0.5px]">BINANCE<span className="text-[#ffffff] font-normal"> AI</span></span>
            <span className="text-[#2b3139]">/</span>
            <span className="text-[#707a8a]">Research</span>
            <span className="text-[#2b3139]">/</span>
            <span className="text-[#ffffff] font-semibold">{upperTicker}</span>
          </div>
          <div className="flex items-center gap-8">
            <Link href={`/forecast/${upperTicker}`} className="nav-link px-3 py-1.5 rounded-md bg-[#fcd535]/10 text-[#fcd535] text-[14px] font-semibold hover:bg-[#fcd535]/20 transition-colors">
              Xem dự báo →
            </Link>
            <button onClick={() => load(true)} className="p-2 rounded-md bg-[#1e2329] border border-[#2b3139] text-[#707a8a] hover:text-[#ffffff] transition-colors">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6 fade-in-up">
          <h1 className="text-[32px] font-bold text-[#ffffff] tracking-[-0.5px]">Research Report — {upperTicker}</h1>
          <p className="text-[#707a8a] text-[14px] mt-1">Phân tích sentiment thị trường bởi Gemini AI Research Agent</p>
        </div>

        {error && (
          <div className="bg-[#1e2329] border border-[#f6465d] p-4 rounded-xl mb-6 text-[#f6465d] text-[14px]">{error}</div>
        )}

        {loading ? (
          <div className="space-y-4">
            <div className="shimmer h-48 rounded-xl" />
            <div className="shimmer h-64 rounded-xl" />
            <div className="shimmer h-40 rounded-xl" />
          </div>
        ) : analysis && (
          <div className="space-y-6 fade-in">
            {/* Main Sentiment Card */}
            <div className={cn("bg-[#1e2329] border border-[#2b3139] p-6 rounded-xl bg-gradient-to-br", sentCfg.bg)}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div style={{ color: sentCfg.color }}>{sentCfg.icon}</div>
                  <div>
                    <div className="text-[12px] text-[#707a8a] font-bold uppercase tracking-wider">Sentiment tổng thể</div>
                    <div className="text-[24px] font-bold mt-1" style={{ color: sentCfg.color }}>{sentCfg.label}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[12px] text-[#707a8a] font-bold uppercase tracking-wider">Độ tin cậy</div>
                  <div className="text-[32px] font-bold font-mono" style={{ color: sentCfg.color }}>
                    {(analysis.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <SentimentGauge score={analysis.sentiment_score} />

              <div className="mt-6 flex items-center gap-2 text-[12px] text-[#707a8a] font-medium">
                <Clock size={14} />
                {analysis.source === "gemini" ? "Phân tích bởi Gemini AI" : "Phân tích keyword tự động"}
                {" · "}
                {new Date(analysis.analyzed_at).toLocaleString("vi-VN")}
                {" · "}
                {analysis.news_count} tin tức
              </div>
            </div>

            {/* Summary */}
            <div className="bg-[#1e2329] border border-[#2b3139] p-6 rounded-xl">
              <h2 className="font-bold text-[#ffffff] text-[18px] mb-3">📝 Tóm tắt phân tích</h2>
              <p className="text-[#eaecef] text-[14px] leading-relaxed">{analysis.summary}</p>
            </div>

            {/* Key Factors + Recommendation */}
            <div className="grid md:grid-cols-2 gap-6">
              {analysis.key_factors.length > 0 && (
                <div className="bg-[#1e2329] border border-[#2b3139] p-6 rounded-xl">
                  <h2 className="font-bold text-[#ffffff] text-[18px] mb-4">🔑 Yếu tố chính</h2>
                  <div className="space-y-3">
                    {analysis.key_factors.map((f, i) => (
                      <div key={i} className="flex items-start gap-3 text-[14px] text-[#eaecef]">
                        <span className="text-[#fcd535] mt-0.5 flex-shrink-0">•</span>
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-[#1e2329] border border-[#2b3139] p-6 rounded-xl">
                <h2 className="font-bold text-[#ffffff] text-[18px] mb-4">💡 Khuyến nghị</h2>
                <p className="text-[#eaecef] text-[14px] leading-relaxed mb-6">{analysis.recommendation}</p>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#707a8a] font-bold uppercase">Mức rủi ro:</span>
                  <span className={cn(
                    "px-3 py-1 rounded text-[12px] font-bold border",
                    analysis.risk_level === "LOW" ? "bg-[#0ecb81]/10 text-[#0ecb81] border-[#0ecb81]/30"
                      : analysis.risk_level === "HIGH" ? "bg-[#f6465d]/10 text-[#f6465d] border-[#f6465d]/30"
                        : "bg-[#fcd535]/10 text-[#fcd535] border-[#fcd535]/30"
                  )}>
                    {analysis.risk_level}
                  </span>
                </div>
              </div>
            </div>

            {/* News Headlines */}
            {analysis.headlines.length > 0 && (
              <div className="bg-[#1e2329] border border-[#2b3139] p-6 rounded-xl">
                <h2 className="font-bold text-[#ffffff] text-[18px] mb-4 flex items-center gap-2">
                  <Newspaper size={18} className="text-[#fcd535]" />
                  Tin tức ({analysis.headlines.length})
                </h2>
                <div className="space-y-3">
                  {analysis.headlines.map((h, i) => (
                    <a key={i} href={h.link} target="_blank" rel="noopener noreferrer"
                      className="flex items-start gap-3 p-4 rounded-lg bg-[#0b0e11] hover:bg-[#2b3139] transition-colors group border border-[#2b3139]">
                      <div className="w-6 h-6 rounded-full bg-[#fcd535]/10 flex-shrink-0 flex items-center justify-center mt-0.5">
                        <span className="text-[12px] font-bold text-[#fcd535]">{i + 1}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] text-[#707a8a] mb-1 font-semibold">{h.source}</div>
                        <div className="text-[14px] text-[#eaecef] group-hover:text-[#ffffff] transition-colors line-clamp-2 font-medium">{h.title}</div>
                      </div>
                      <ExternalLink size={16} className="text-[#707a8a] group-hover:text-[#fcd535] flex-shrink-0 mt-1 transition-colors" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            <p className="text-center text-xs text-[#2b3139]">
              ⚠️ Phân tích AI chỉ mang tính tham khảo, không phải lời khuyên đầu tư.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
