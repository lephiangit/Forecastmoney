"use client";

import { useEffect, useState, useRef, use } from "react";
import Link from "next/link";
import { forecastApi, type CombinedForecastResponse } from "@/lib/api";
import {
  TrendingUp, TrendingDown, ArrowLeft, RefreshCw,
  AlertTriangle, Newspaper, Brain, ChevronDown
} from "lucide-react";
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  Area, ComposedChart, Bar, Cell, Line,
  CartesianGrid
} from "recharts";

function cn(...c: (string | false | undefined)[]) { return c.filter(Boolean).join(" "); }

// ── Count-Up Hook ───────────────────────────────────────────────────────────
function useCountUp(target: number, duration = 800) {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(0);
  const rafRef = useRef<number>(0);
  useEffect(() => {
    const start = prevTarget.current;
    const diff = target - start;
    if (Math.abs(diff) < 0.001) { setValue(target); return; }
    const startTime = performance.now();
    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 5);
      setValue(start + diff * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
      else prevTarget.current = target;
    }
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);
  return value;
}

function CountUpPrice({ value, format }: { value: number; format: (v: number) => string }) {
  const animated = useCountUp(value, 1000);
  return <span>{format(animated)}</span>;
}

// ── Sentiment Badge ───────────────────────────────────────────────────────────
function SentimentBadge({ sentiment, confidence }: { sentiment: string; confidence: number }) {
  const cfg = {
    BULLISH: { color: "text-[#03a66d]", bg: "bg-[#03a66d]/10 border-[#03a66d]/30", label: "Tích cực", icon: <TrendingUp size={12} /> },
    BEARISH: { color: "text-[#cf304a]", bg: "bg-[#cf304a]/10 border-[#cf304a]/30", label: "Tiêu cực", icon: <TrendingDown size={12} /> },
    NEUTRAL: { color: "text-[#f0b90b]", bg: "bg-[#f0b90b]/10 border-[#f0b90b]/30", label: "Trung tính", icon: <AlertTriangle size={12} /> },
  }[sentiment] || { color: "text-[#848e9c]", bg: "bg-[#848e9c]/10 border-[#848e9c]/30", label: "N/A", icon: null };

  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-bold border", cfg.color, cfg.bg)}>
      {cfg.icon}
      {cfg.label} {(confidence * 100).toFixed(0)}%
    </span>
  );
}

// ── Risk Badge ────────────────────────────────────────────────────────────────
function RiskBadge({ level }: { level: string }) {
  const cfg = {
    LOW: "text-[#0ecb81] bg-[#0ecb81]/10 border border-[#0ecb81]/30",
    MEDIUM: "text-[#fcd535] bg-[#fcd535]/10 border border-[#fcd535]/30",
    HIGH: "text-[#f6465d] bg-[#f6465d]/10 border border-[#f6465d]/30",
  }[level] || "text-[#707a8a] bg-[#707a8a]/10 border border-[#707a8a]/30";
  return <span className={cn("px-2 py-0.5 rounded text-xs font-bold", cfg)}>{level}</span>;
}

// ── Custom Candlestick Shape ──────────────────────────────────────────────────
// (Removed CandlestickRenderer as it is currently unused)

// ═══════════════════════════════════════════════════════════════════════════════
// CHART 1: Biểu đồ NẾN (Candlestick) — Lịch sử + Dự báo kéo dài
// ═══════════════════════════════════════════════════════════════════════════════
function CandlestickLineChart({
  forecast, currentPrice
}: {
  forecast: CombinedForecastResponse; currentPrice: number;
}) {
  const histBars = (forecast.historical || []).slice(-30);
  const tftMedian = forecast.tft.median || [];

  const chartData: Record<string, unknown>[] = [];

  // Historical data — candlesticks
  histBars.forEach((bar) => {
    chartData.push({
      date: bar.date.slice(5),
      fullDate: bar.date,
      isCandle: true,
      open: bar.open, high: bar.high, low: bar.low, close: bar.close,
      priceHigh: bar.high, priceLow: bar.low,
    });
  });

  // Forecast — đường nối tiếp (tft + sf)
  tftMedian.forEach((p, i) => {
    const sfPrice = forecast.sentiment_fusion.median?.[i]?.price;
    chartData.push({
      date: p.date.slice(5),
      fullDate: p.date,
      isCandle: false,
      tft: p.price,
      sf: sfPrice,
      tft_upper: forecast.tft.upper_q90?.[i]?.price,
      tft_lower: forecast.tft.lower_q10?.[i]?.price,
    });
  });

  // Y domain
  const allPrices = chartData.flatMap(d => {
    const p: number[] = [];
    if (d.isCandle) { p.push(d.high, d.low); }
    if (d.tft) p.push(d.tft);
    if (d.tft_upper) p.push(d.tft_upper);
    if (d.tft_lower) p.push(d.tft_lower);
    if (d.sf) p.push(d.sf);
    return p;
  });
  allPrices.push(currentPrice);
  const minY = Math.min(...allPrices) * 0.997;
  const maxY = Math.max(...allPrices) * 1.003;

  const fmt = (v: number) => currentPrice > 1000
    ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : v.toFixed(4);

  const divideIdx = histBars.length;

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
        <defs>
          <linearGradient id="tftBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fcd535" stopOpacity={0.12} />
            <stop offset="95%" stopColor="#fcd535" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2329" />
        <XAxis dataKey="date" tick={{ fill: "#707a8a", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis domain={[minY, maxY]} tick={{ fill: "#707a8a", fontSize: 10 }} tickFormatter={fmt} width={70} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: "#1e2329", border: "1px solid #2b3139", borderRadius: "8px", color: "#fff", fontSize: 12 }}
          formatter={(v: unknown, name: unknown) => [fmt(Number(v)), name === "tft" ? "TFT" : name === "sf" ? "SF" : name === "close" ? "Close" : String(name)]}
          labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ""}
        />

        {/* Historical candlestick bars (close price for height, colored by direction) */}
        <Bar dataKey="close" barSize={6} isAnimationActive={false}>
          {chartData.map((entry, index) => {
            if (!entry.isCandle) return <Cell key={index} fill="transparent" stroke="transparent" />;
            const isUp = entry.close >= entry.open;
            return <Cell key={index} fill={isUp ? "#0ecb81" : "#f6465d"} stroke={isUp ? "#0ecb81" : "#f6465d"} />;
          })}
        </Bar>

        {/* Divider */}
        {divideIdx > 0 && divideIdx < chartData.length && (
          <ReferenceLine x={chartData[divideIdx - 1]?.date} stroke="#fcd535" strokeDasharray="4 4" strokeOpacity={0.5}
            label={{ value: "▸ Dự báo", fill: "#fcd535", fontSize: 10, position: "top" }} />
        )}
        <ReferenceLine y={currentPrice} stroke="#707a8a" strokeDasharray="4 2"
          label={{ value: `${fmt(currentPrice)}`, fill: "#707a8a", fontSize: 10 }} />

        {/* Forecast band */}
        <Area type="monotone" dataKey="tft_upper" stroke="none" fill="url(#tftBand)" connectNulls={false} isAnimationActive={true} animationDuration={1200} />
        {/* TFT forecast line */}
        <Line type="monotone" dataKey="tft" stroke="#fcd535" strokeWidth={2.5}
          dot={{ r: 3, fill: "#fcd535", strokeWidth: 0 }}
          activeDot={{ r: 5, fill: "#fcd535", stroke: "#0b0e11", strokeWidth: 2 }}
          connectNulls={false} isAnimationActive={true} animationDuration={1500} name="tft" />
        {/* SF forecast line */}
        {forecast.sentiment_fusion.median && (
          <Line type="monotone" dataKey="sf" stroke="#3861fb" strokeWidth={2} strokeDasharray="6 3"
            dot={{ r: 2, fill: "#3861fb", strokeWidth: 0 }} connectNulls={false}
            isAnimationActive={true} animationDuration={1500} name="sf" />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHART 2: Biểu đồ CỘT DỰ BÁO (Tăng Xanh / Giảm Đỏ) — cùng kiểu với lịch sử
// ═══════════════════════════════════════════════════════════════════════════════
function ForecastBarChart({
  forecast, currentPrice
}: {
  forecast: CombinedForecastResponse; currentPrice: number;
}) {
  const histBars = (forecast.historical || []).slice(-30);
  const tftMedian = forecast.tft.median || [];

  const chartData: Record<string, unknown>[] = [];

  // Historical — cột xanh/đỏ dựa trên close vs open
  histBars.forEach((bar) => {
    const isUp = bar.close >= bar.open;
    chartData.push({
      date: bar.date.slice(5),
      fullDate: bar.date,
      section: "history",
      barValue: bar.close,
      color: isUp ? "#0ecb81" : "#f6465d",
      isUp,
    });
  });

  // Forecast — cột xanh/đỏ dựa trên giá dự báo so với giá hôm trước
  tftMedian.forEach((p, i) => {
    const prevPrice = i === 0 ? currentPrice : (tftMedian[i - 1]?.price || currentPrice);
    const isUp = p.price >= prevPrice;
    chartData.push({
      date: p.date.slice(5),
      fullDate: p.date,
      section: "forecast",
      barValue: p.price,
      color: isUp ? "#0ecb81" : "#f6465d",
      isUp,
      // Make forecast bars slightly transparent
      opacity: 0.7,
    });
  });

  const allPrices = chartData.map(d => d.barValue);
  const minY = Math.min(...allPrices) * 0.997;
  const maxY = Math.max(...allPrices) * 1.003;

  const fmt = (v: number) => currentPrice > 1000
    ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : v.toFixed(4);

  const divideIdx = histBars.length;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2329" />
        <XAxis dataKey="date" tick={{ fill: "#707a8a", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis domain={[minY, maxY]} tick={{ fill: "#707a8a", fontSize: 10 }} tickFormatter={fmt} width={70} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: "#1e2329", border: "1px solid #2b3139", borderRadius: "8px", color: "#fff", fontSize: 12 }}
          formatter={(v: unknown) => [fmt(Number(v)), "Giá"]}
          labelFormatter={(_, payload) => {
            const d = payload?.[0]?.payload;
            if (!d) return "";
            return `${d.fullDate} (${d.section === "forecast" ? "Dự báo" : "Lịch sử"})`;
          }}
        />

        {/* Divider */}
        {divideIdx > 0 && divideIdx < chartData.length && (
          <ReferenceLine x={chartData[divideIdx - 1]?.date} stroke="#fcd535" strokeDasharray="4 4" strokeOpacity={0.5}
            label={{ value: "▸ Dự báo", fill: "#fcd535", fontSize: 10, position: "top" }} />
        )}
        <ReferenceLine y={currentPrice} stroke="#707a8a" strokeDasharray="4 2"
          label={{ value: `Hiện tại: ${fmt(currentPrice)}`, fill: "#707a8a", fontSize: 10 }} />

        {/* Bars — xanh tăng, đỏ giảm */}
        <Bar dataKey="barValue" barSize={10} isAnimationActive={true} animationDuration={1200}>
          {chartData.map((entry, index) => (
            <Cell
              key={index}
              fill={entry.color}
              fillOpacity={entry.section === "forecast" ? 0.55 : 1}
              stroke={entry.color}
              strokeWidth={entry.section === "forecast" ? 1 : 0}
              strokeDasharray={entry.section === "forecast" ? "3 2" : "none"}
            />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── PnL Forecast ──────────────────────────────────────────────────────────────
function PnLForecast({ currentPrice, forecastPrice, label }: { currentPrice: number; forecastPrice: number; label: string }) {
  const diff = forecastPrice - currentPrice;
  const pct = (diff / currentPrice) * 100;
  const isPositive = diff >= 0;
  const investAmount = 1000;
  const pnl = investAmount * (pct / 100);

  return (
    <div className="bg-[#0b0e11] rounded-lg p-3 border border-[#2b3139]">
      <div className="text-[10px] text-[#707a8a] mb-1 uppercase tracking-wider font-semibold">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className={cn("text-lg font-bold font-mono", isPositive ? "text-[#0ecb81]" : "text-[#f6465d]")}>
          {isPositive ? "+" : ""}{pct.toFixed(2)}%
        </span>
        <span className="text-xs text-[#707a8a] font-mono">
          ({isPositive ? "+" : ""}${pnl.toFixed(2)} / $1,000)
        </span>
      </div>
    </div>
  );
}

// ── Collapsible Section ───────────────────────────────────────────────────────
function CollapsibleSection({ title, icon, defaultOpen = false, children }: {
  title: string; icon: React.ReactNode; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-[#1e2329] rounded-xl border border-[#2b3139] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 hover:bg-[#2b3139]/30 transition-colors"
      >
        <div className="flex items-center gap-2 font-bold text-[#ffffff] text-[16px]">
          {icon} {title}
        </div>
        <div className={cn("text-[#707a8a] transition-transform duration-300", open && "rotate-180")}>
          <ChevronDown size={18} />
        </div>
      </button>
      <div className={cn(
        "transition-all duration-400 overflow-hidden",
        open ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
      )}>
        <div className="px-5 pb-5">
          {children}
        </div>
      </div>
    </div>
  );
}

// ── Days Slider ───────────────────────────────────────────────────────────────
function DaysSlider({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const steps = [3, 7, 14, 30];
  const idx = steps.indexOf(value);
  const pct = (idx / (steps.length - 1)) * 100;

  return (
    <div className="flex items-center gap-4 w-full max-w-xs">
      <span className="text-[#707a8a] text-[13px] font-semibold whitespace-nowrap">Dự báo:</span>
      <div className="relative flex-1">
        {/* Track */}
        <div className="h-1.5 bg-[#2b3139] rounded-full relative">
          <div className="absolute h-full bg-[#fcd535] rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }} />
        </div>
        {/* Tick marks */}
        <div className="flex justify-between mt-1.5">
          {steps.map((s) => (
            <button
              key={s}
              onClick={() => onChange(s)}
              className={cn(
                "text-[11px] font-bold font-mono transition-all px-1.5 py-0.5 rounded",
                value === s ? "text-[#181a20] bg-[#fcd535]" : "text-[#707a8a] hover:text-[#ffffff]"
              )}
            >
              {s}d
            </button>
          ))}
        </div>
        {/* Hidden range input for dragging */}
        <input
          type="range"
          min={0} max={steps.length - 1}
          value={idx >= 0 ? idx : 1}
          onChange={(e) => onChange(steps[parseInt(e.target.value)])}
          className="absolute inset-0 w-full opacity-0 cursor-pointer"
          style={{ height: "24px", top: "-4px" }}
        />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function ForecastPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const upperTicker = ticker.toUpperCase();

  const [days, setDays] = useState(7);
  const [forecast, setForecast] = useState<CombinedForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const fc = await forecastApi.combined(upperTicker, days);
      setForecast(fc);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message || "Lỗi tải dữ liệu");
      else setError("Lỗi tải dữ liệu");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [upperTicker, days]); // eslint-disable-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect

  const currentPrice = forecast?.live?.price || forecast?.current_price || 0;
  const isCrypto = !upperTicker.endsWith(".VN");
  const fmtPrice = (p: number) => isCrypto
    ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : p.toLocaleString("vi-VN");

  const tftFinal = forecast?.tft.median?.at(-1)?.price;
  const sfFinal = forecast?.sentiment_fusion.median?.at(-1)?.price;
  const tftPct = tftFinal && currentPrice ? (tftFinal - currentPrice) / currentPrice * 100 : null;
  const sfPct = sfFinal && currentPrice ? (sfFinal - currentPrice) / currentPrice * 100 : null;

  return (
    <div className="min-h-screen bg-[#0b0e11]">
      {/* Nav */}
      <nav className="navbar-sticky sticky top-0 z-50 border-b border-[#2b3139]">
        <div className="max-w-7xl mx-auto px-4 h-[64px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-[#707a8a] hover:text-[#ffffff] transition-colors">
              <ArrowLeft size={20} />
            </Link>
            <span className="font-bold text-[#fcd535] text-[20px] tracking-[-0.5px]">BINANCE<span className="text-[#ffffff] font-normal"> AI</span></span>
            <span className="text-[#2b3139]">/</span>
            <span className="text-[#ffffff] font-semibold">{upperTicker}</span>
          </div>
          <div className="flex items-center gap-8 text-[14px] font-medium">
            <Link href="/" className="nav-link text-[#eaecef] hover:text-[#fcd535] transition-colors">Dashboard</Link>
            <Link href={`/research/${upperTicker}`} className="nav-link text-[#eaecef] hover:text-[#fcd535] transition-colors">Research</Link>
            <Link href="/admin" className="nav-link text-[#eaecef] hover:text-[#fcd535] transition-colors">Trading</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 fade-in-up">
          <div>
            <h1 className="text-[32px] font-bold text-[#ffffff] tracking-[-0.5px]">
              {upperTicker} — Dự báo Giá AI
            </h1>
            <p className="text-[#707a8a] text-[14px] mt-1">
              Biểu đồ nến lịch sử + Cột dự báo tăng/giảm + TFT &amp; SentimentFusion
            </p>
          </div>

          {/* Days slider */}
          <div className="flex items-center gap-3">
            <DaysSlider value={days} onChange={setDays} />
            <button onClick={load} className="p-2 rounded-md bg-[#1e2329] border border-[#2b3139] text-[#707a8a] hover:text-[#ffffff] transition-colors">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-[#1e2329] border border-[#f6465d] p-4 rounded-xl mb-6 text-[#f6465d] text-[14px] flex items-center gap-2 fade-in">
            <AlertTriangle size={16} /> {error}
            <button onClick={load} className="ml-auto font-semibold hover:underline">Thử lại</button>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => <div key={i} className="shimmer h-32 rounded-xl" />)}
          </div>
        ) : forecast && (
          <div className="space-y-6 fade-in">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger-children">
              <div className="card-micro bg-[#1e2329] p-4 rounded-xl border border-[#2b3139] transition-all duration-300">
                <div className="text-[12px] text-[#707a8a] mb-1">Giá hiện tại</div>
                <div className="text-[24px] font-bold text-[#ffffff] font-mono">
                  <CountUpPrice value={currentPrice} format={fmtPrice} />
                </div>
                <div className="text-[12px] text-[#707a8a]">{isCrypto ? "USD" : "VNĐ"}</div>
              </div>

              {tftFinal && tftPct !== null && (
                <div className="card-micro bg-[#1e2329] p-4 rounded-xl border border-[#2b3139] transition-all duration-300">
                  <div className="text-[12px] text-[#707a8a] mb-1 flex items-center gap-1 font-semibold">
                    <Brain size={12} className="text-[#fcd535]" /> TFT (ngày {days})
                  </div>
                  <div className="text-[24px] font-bold text-[#ffffff] font-mono">
                    <CountUpPrice value={tftFinal} format={fmtPrice} />
                  </div>
                  <div className={cn("text-[14px] font-semibold", tftPct >= 0 ? "text-[#0ecb81]" : "text-[#f6465d]")}>
                    {tftPct >= 0 ? "▲" : "▼"} {Math.abs(tftPct).toFixed(2)}%
                  </div>
                </div>
              )}

              {sfFinal && sfPct !== null && (
                <div className="card-micro bg-[#1e2329] p-4 rounded-xl border border-[#2b3139] transition-all duration-300">
                  <div className="text-[12px] text-[#707a8a] mb-1 flex items-center gap-1 font-semibold">
                    <Newspaper size={12} className="text-[#3b82f6]" /> SentimentFusion (ngày {days})
                  </div>
                  <div className="text-[24px] font-bold text-[#ffffff] font-mono">
                    <CountUpPrice value={sfFinal} format={fmtPrice} />
                  </div>
                  <div className={cn("text-[14px] font-semibold", sfPct >= 0 ? "text-[#0ecb81]" : "text-[#f6465d]")}>
                    {sfPct >= 0 ? "▲" : "▼"} {Math.abs(sfPct).toFixed(2)}%
                  </div>
                </div>
              )}

              {forecast.research && (
                <div className="card-micro bg-[#1e2329] p-4 rounded-xl border border-[#2b3139] transition-all duration-300">
                  <div className="text-[12px] text-[#707a8a] mb-2">Sentiment thị trường</div>
                  <SentimentBadge sentiment={forecast.research.sentiment} confidence={forecast.research.confidence} />
                  <div className="mt-2">
                    <RiskBadge level={forecast.research.risk_level} />
                  </div>
                </div>
              )}
            </div>

            {/* PnL Forecast */}
            {(tftFinal || sfFinal) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {tftFinal && (
                  <PnLForecast currentPrice={currentPrice} forecastPrice={tftFinal} label={`Lãi/Lỗ dự báo TFT (${days} ngày)`} />
                )}
                {sfFinal && (
                  <PnLForecast currentPrice={currentPrice} forecastPrice={sfFinal} label={`Lãi/Lỗ dự báo SentimentFusion (${days} ngày)`} />
                )}
              </div>
            )}

            {/* ═══ CHART 1: Biểu đồ Nến + Dự báo đường ═══ */}
            <div className="bg-[#1e2329] p-6 rounded-xl border border-[#2b3139] scale-in">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-[#ffffff] text-[18px]">📈 Biểu đồ Nến + Đường dự báo</h2>
                <div className="flex items-center gap-4 text-[11px] text-[#707a8a] font-semibold">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#0ecb81] inline-block rounded-sm" /> Tăng</span>
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#f6465d] inline-block rounded-sm" /> Giảm</span>
                  <span className="flex items-center gap-1.5"><span className="w-4 h-0.5 bg-[#fcd535] inline-block rounded-full" /> TFT</span>
                  <span className="flex items-center gap-1.5"><span className="w-4 h-0.5 bg-[#3b82f6] inline-block rounded-full border-dashed" /> SF</span>
                </div>
              </div>
              <CandlestickLineChart forecast={forecast} currentPrice={currentPrice} />
            </div>

            {/* ═══ CHART 2: Biểu đồ cột tăng/giảm (Lịch sử + Dự báo) ═══ */}
            <div className="bg-[#1e2329] p-6 rounded-xl border border-[#2b3139] scale-in">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-[#ffffff] text-[18px]">📊 Biểu đồ Cột Tăng/Giảm (Lịch sử + Dự báo)</h2>
                <div className="flex items-center gap-4 text-[11px] text-[#707a8a] font-semibold">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#0ecb81] inline-block rounded-sm" /> Tăng</span>
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#f6465d] inline-block rounded-sm" /> Giảm</span>
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#0ecb81]/50 inline-block rounded-sm border border-dashed border-[#0ecb81]" /> Dự báo</span>
                </div>
              </div>
              <ForecastBarChart forecast={forecast} currentPrice={currentPrice} />
            </div>

            {/* ═══ Research Agent — Collapsible ═══ */}
            {forecast.research && (
              <CollapsibleSection
                title="Phân tích Research Agent"
                icon={<Newspaper size={18} className="text-[#fcd535]" />}
                defaultOpen={false}
              >
                <div className="space-y-5">
                  <p className="text-[#eaecef] text-[14px] leading-[1.8]">{forecast.research.summary}</p>

                  {forecast.research.key_factors.length > 0 && (
                    <div>
                      <div className="text-[12px] text-[#707a8a] mb-3 font-bold uppercase tracking-wider">Yếu tố chính</div>
                      <div className="space-y-2.5">
                        {forecast.research.key_factors.map((f, i) => (
                          <div key={i} className="flex items-start gap-3 text-[14px] text-[#eaecef] leading-[1.6]">
                            <span className="text-[#fcd535] mt-0.5 flex-shrink-0">•</span>
                            <span>{f}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="p-4 bg-[#2b3139]/40 rounded-lg border border-[#2b3139]">
                    <div className="text-[12px] text-[#707a8a] mb-2 font-bold uppercase tracking-wider">Khuyến nghị từ AI</div>
                    <div className="text-[14px] text-[#ffffff] font-medium leading-[1.6]">{forecast.research.recommendation}</div>
                  </div>

                  {forecast.research.headlines.length > 0 && (
                    <div>
                      <div className="text-[12px] text-[#707a8a] mb-3 font-bold uppercase tracking-wider">Tin tức liên quan</div>
                      <div className="space-y-1">
                        {forecast.research.headlines.map((h: { link: string, source: string, title: string }, i: number) => (
                          <a key={i} href={h.link} target="_blank" rel="noopener noreferrer"
                            className="block p-3 rounded-lg hover:bg-[#2b3139] transition-all table-row-hover">
                            <div className="text-[11px] text-[#707a8a] group-hover:text-[#fcd535] transition-colors">{h.source}</div>
                            <div className="text-[13px] text-[#eaecef] font-medium mt-1 leading-[1.5]">{h.title}</div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="text-right pt-2">
                    <Link href={`/research/${upperTicker}`} className="text-[14px] text-[#fcd535] font-semibold hover:underline nav-link">
                      Xem đầy đủ báo cáo research →
                    </Link>
                  </div>
                </div>
              </CollapsibleSection>
            )}

            {/* Forecast tables — Collapsible */}
            <div className="grid md:grid-cols-2 gap-6">
              {forecast.tft.median && (
                <CollapsibleSection
                  title="TFT — Bảng dự báo"
                  icon={<Brain size={18} className="text-[#fcd535]" />}
                  defaultOpen={false}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead>
                        <tr className="text-[#707a8a] border-b border-[#2b3139]">
                          <th className="text-left py-2 font-semibold">Ngày</th>
                          <th className="text-right py-2 font-semibold">Giá dự báo</th>
                          <th className="text-right py-2 font-semibold">Khoảng</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forecast.tft.median.map((p, i) => {
                          const pct = (p.price - currentPrice) / currentPrice * 100;
                          const lower = forecast.tft.lower_q10?.[i]?.price;
                          const upper = forecast.tft.upper_q90?.[i]?.price;
                          return (
                            <tr key={i} className="border-b border-[#2b3139] table-row-hover font-mono">
                              <td className="py-3 text-[#707a8a]">{p.date}</td>
                              <td className="py-3 text-right">
                                <span className="text-[#ffffff] font-bold">{fmtPrice(p.price)}</span>
                                <span className={cn("ml-2 text-[12px] font-semibold", pct >= 0 ? "text-[#0ecb81]" : "text-[#f6465d]")}>
                                  {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
                                </span>
                              </td>
                              <td className="py-3 text-right text-[12px] text-[#707a8a]">
                                {lower && upper ? `${fmtPrice(lower)} – ${fmtPrice(upper)}` : "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CollapsibleSection>
              )}

              {forecast.sentiment_fusion.median && (
                <CollapsibleSection
                  title="SentimentFusion — Bảng dự báo"
                  icon={<Newspaper size={18} className="text-[#3b82f6]" />}
                  defaultOpen={false}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead>
                        <tr className="text-[#707a8a] border-b border-[#2b3139]">
                          <th className="text-left py-2 font-semibold">Ngày</th>
                          <th className="text-right py-2 font-semibold">Giá dự báo</th>
                          <th className="text-right py-2 font-semibold">% Thay đổi</th>
                        </tr>
                      </thead>
                      <tbody>
                        {forecast.sentiment_fusion.median.map((p, i) => {
                          const tftP = forecast.tft.median?.[i]?.price;
                          const diff = tftP ? p.price - tftP : 0;
                          const pct = (p.price - currentPrice) / currentPrice * 100;
                          return (
                            <tr key={i} className="border-b border-[#2b3139] table-row-hover font-mono">
                              <td className="py-3 text-[#707a8a]">{p.date}</td>
                              <td className="py-3 text-right">
                                <span className="text-[#ffffff] font-bold">{fmtPrice(p.price)}</span>
                                {diff !== 0 && (
                                  <span className={cn("ml-2 text-[12px] font-semibold", diff > 0 ? "text-[#0ecb81]" : "text-[#f6465d]")}>
                                    ({diff > 0 ? "+" : ""}{fmtPrice(diff)})
                                  </span>
                                )}
                              </td>
                              <td className={cn("py-3 text-right text-[14px] font-bold", pct >= 0 ? "text-[#0ecb81]" : "text-[#f6465d]")}>
                                {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CollapsibleSection>
              )}
            </div>

            <p className="text-center text-xs text-[#2b3139]">
              Dự báo AI chỉ mang tính tham khảo — không phải lời khuyên đầu tư.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
