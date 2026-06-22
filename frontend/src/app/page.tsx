"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { marketApi, type LiveQuote, type TickerSearchResult } from "@/lib/api";
import {
  TrendingUp, TrendingDown, BarChart2, Activity,
  Search, RefreshCw, Plus, X, Loader2
} from "lucide-react";

function cn(...c: (string | false | undefined)[]) { return c.filter(Boolean).join(" "); }

const DEFAULT_TICKERS = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD", "DOGE-USD", "AVAX-USD"];
const REFRESH_MS = 60_000;
const STORAGE_KEY = "forecastai_watchlist";

function loadWatchlist(): string[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : DEFAULT_TICKERS;
  } catch { return DEFAULT_TICKERS; }
}
function saveWatchlist(list: string[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch {}
}

// ── Count-Up Animation Hook ──────────────────────────────────────────────────
function useCountUp(target: number, duration = 1000, decimals = 2) {
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
      // ease-out-quint
      const eased = 1 - Math.pow(1 - progress, 5);
      setValue(start + diff * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
      else prevTarget.current = target;
    }
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return decimals > 0 ? value.toFixed(decimals) : Math.round(value).toString();
}

// ── Price Range Bar (High-Low Indicator) ────────────────────────────────────
function PriceRangeBar({ low, high, current }: { low: number; high: number; current: number }) {
  const range = high - low;
  const pct = range > 0 ? ((current - low) / range) * 100 : 50;
  const clampedPct = Math.max(2, Math.min(98, pct));

  return (
    <div className="mt-2.5">
      <div className="flex justify-between text-[9px] text-[#707a8a] mb-1">
        <span>Low</span>
        <span>High</span>
      </div>
      <div className="range-bar">
        <div className="range-bar-dot" style={{ left: `${clampedPct}%` }} />
      </div>
    </div>
  );
}

// ── Live Price Card ─────────────────────────────────────────────────────────
function PriceCard({ item, onRemove }: { item: LiveQuote; onRemove?: () => void }) {
  const isUp = item.change_pct >= 0;
  const fmtPrice = (p: number) => p >= 1
    ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : p.toFixed(6);

  return (
    <div className="relative group">
      <Link href={`/forecast/${item.ticker}`} className="block">
        <div className="card-hover bg-[#1e2329] p-4 rounded-xl hover:border-[#fcd535]/40 border border-[#2b3139] cursor-pointer">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="min-w-0">
              <div className="text-[10px] text-[#707a8a] uppercase tracking-widest font-mono">{item.ticker}</div>
              <div className="text-sm font-bold text-[#ffffff] mt-0.5 truncate max-w-[120px]">
                {item.name || item.ticker}
              </div>
            </div>
            <div className={cn(
              "flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0",
              isUp ? "text-[#0ecb81] bg-[#0ecb81]/10" : "text-[#f6465d] bg-[#f6465d]/10"
            )}>
              {isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
              {item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
            </div>
          </div>

          {/* Price */}
          <div className="mb-1">
            <span className="text-xl font-bold text-[#ffffff] font-mono">{fmtPrice(item.price)}</span>
            <span className="text-xs text-[#707a8a] ml-1 font-mono">USD</span>
          </div>

          {/* 24h High-Low with visual range bar */}
          <PriceRangeBar low={item.low} high={item.high} current={item.price} />

          {/* High / Low Numbers */}
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <div className="text-[9px] text-[#707a8a] uppercase">High</div>
              <div className="text-xs text-[#0ecb81] font-mono font-semibold">{fmtPrice(item.high)}</div>
            </div>
            <div className="text-right">
              <div className="text-[9px] text-[#707a8a] uppercase">Low</div>
              <div className="text-xs text-[#f6465d] font-mono font-semibold">{fmtPrice(item.low)}</div>
            </div>
          </div>
        </div>
      </Link>

      {/* Remove button */}
      {onRemove && (
        <button
          onClick={e => { e.preventDefault(); onRemove(); }}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-[#1e2329] border border-[#2b3139] text-[#707a8a] opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-10 hover:bg-[#f6465d] hover:text-[#ffffff] hover:border-[#f6465d]"
        >
          <X size={10} />
        </button>
      )}
    </div>
  );
}

// ── Ticker Search Dialog ────────────────────────────────────────────────────
function AddTickerDialog({ onAdd, open, onClose }: {
  onAdd: (ticker: string) => void;
  open: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const res = await marketApi.search(q);
      setResults(res.results);
    } catch { setResults([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => doSearch(query), 400);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query, doSearch]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop bg-black/60">
      <div className="bg-[#1e2329] rounded-xl w-full max-w-md p-6 shadow-2xl modal-content border border-[#2b3139]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-[#ffffff]">Thêm tài sản vào watchlist</h2>
          <button onClick={onClose} className="text-[#707a8a] hover:text-[#ffffff] transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#707a8a]" />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Tìm BTC, ETH, AAPL, VIC.VN..."
            className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-lg pl-9 pr-4 py-2.5 text-sm text-[#ffffff] placeholder-[#707a8a] focus:outline-none focus:border-[#fcd535] transition-colors"
          />
          {loading && <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#707a8a] animate-spin" />}
        </div>

        <div className="space-y-1 max-h-72 overflow-y-auto">
          {results.length === 0 && query.length > 0 && !loading && (
            <div className="text-center py-6 text-[#707a8a] text-sm">
              Không tìm thấy kết quả — thử nhập trực tiếp (vd: DOGE-USD)
              <button
                onClick={() => { onAdd(query.toUpperCase()); onClose(); }}
                className="block mx-auto mt-2 text-[#fcd535] text-xs hover:underline font-semibold"
              >
                Thêm &quot;{query.toUpperCase()}&quot; trực tiếp →
              </button>
            </div>
          )}
          {results.map(r => (
            <button
              key={r.symbol}
              onClick={() => { onAdd(r.symbol); onClose(); }}
              className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-[#2b3139] transition-all text-left group"
            >
              <div className="w-8 h-8 rounded-full bg-[#2b3139] group-hover:bg-[#fcd535] flex items-center justify-center flex-shrink-0 transition-colors">
                <BarChart2 size={14} className="text-[#707a8a] group-hover:text-[#181a20]" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-mono font-semibold text-[#ffffff]">{r.symbol}</div>
                <div className="text-xs text-[#707a8a] truncate">{r.name} · {r.exchange}</div>
              </div>
              <span className="text-[10px] text-[#707a8a] bg-[#2b3139] px-1.5 py-0.5 rounded flex-shrink-0">
                {r.type}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── CountUp Display Component ───────────────────────────────────────────────
function CountUpValue({ value, decimals = 0, className = "" }: { value: number; decimals?: number; className?: string }) {
  const displayed = useCountUp(value, 800, decimals);
  return <span className={className}>{displayed}</span>;
}

// ── Dashboard ───────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [watchlist, setWatchlist] = useState<string[]>(DEFAULT_TICKERS);
  const [quotes, setQuotes] = useState<Map<string, LiveQuote>>(new Map());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [filter, setFilter] = useState<"all" | "crypto" | "stock">("all");
  const [hasToken, setHasToken] = useState(false);

  // Load watchlist from localStorage on mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setWatchlist(loadWatchlist());
    setHasToken(!!localStorage.getItem("forecast_ai_token"));
  }, []);

  const fetchAll = useCallback(async (tickers: string[], isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await marketApi.overview(tickers);
      const newMap = new Map<string, LiveQuote>();
      res.data.forEach(q => newMap.set(q.ticker, q));
      setQuotes(newMap);
      setLastUpdate(new Date());
    } catch (e) {
      console.error("Fetch error:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial + interval refresh
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchAll(watchlist);
    const id = setInterval(() => fetchAll(watchlist, true), REFRESH_MS);
    return () => clearInterval(id);
  }, [watchlist, fetchAll]);

  const addTicker = useCallback((ticker: string) => {
    const upper = ticker.toUpperCase();
    if (!watchlist.includes(upper)) {
      const next = [...watchlist, upper];
      setWatchlist(next);
      saveWatchlist(next);
      fetchAll(next, true);
    }
  }, [watchlist, fetchAll]);

  const removeTicker = useCallback((ticker: string) => {
    const next = watchlist.filter(t => t !== ticker);
    setWatchlist(next);
    saveWatchlist(next);
    setQuotes(prev => { const m = new Map(prev); m.delete(ticker); return m; });
  }, [watchlist]);

  // Filter display
  const displayTickers = watchlist.filter(t => {
    if (filter === "all") return true;
    if (filter === "crypto") return t.endsWith("-USD");
    if (filter === "stock") return !t.endsWith("-USD");
    return true;
  });

  const displayQuotes = displayTickers.map(t => quotes.get(t)).filter(Boolean) as LiveQuote[];
  const upCount = displayQuotes.filter(q => q.change_pct >= 0).length;
  const downCount = displayQuotes.length - upCount;

  return (
    <div className="min-h-screen bg-[#0b0e11]">
      {/* Add ticker dialog */}
      <AddTickerDialog open={showAdd} onAdd={addTicker} onClose={() => setShowAdd(false)} />

      {/* Navbar */}
      <nav className="navbar-sticky sticky top-0 z-40 border-b border-[#2b3139]">
        <div className="max-w-7xl mx-auto px-4 h-[64px] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 flex items-center justify-center text-[#fcd535]">
              <TrendingUp size={24} />
            </div>
            <span className="font-bold text-[24px] text-[#fcd535] tracking-[-0.5px]">BINANCE<span className="text-[#ffffff] font-normal"> AI</span></span>
          </div>
          <div className="flex items-center gap-8 text-[14px] font-medium">
            <Link href="/" className="nav-link nav-link-active text-[#fcd535]">Dashboard</Link>
            <Link href="/research" className="nav-link text-[#eaecef] hover:text-[#fcd535] transition-colors">Research</Link>
            {hasToken ? (
              <Link href="/admin" className="nav-link text-[#eaecef] hover:text-[#fcd535] transition-colors">Trading</Link>
            ) : (
              <Link href="/login" className="btn-primary px-5 py-2 rounded-lg text-[14px] font-semibold hover:bg-[#f0b90b] transition-colors">Đăng nhập</Link>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-[80px]">
        {/* Header */}
        <div className="mb-[48px] text-center fade-in-up">
          <h1 className="text-[48px] font-bold text-[#ffffff] tracking-[-0.5px] leading-[1.1]">Market Intelligence</h1>
          <p className="text-[#707a8a] text-[16px] mt-4 max-w-2xl mx-auto">
            Real-time AI research + TFT &amp; SentimentFusion forecasting — hỗ trợ mọi mã giao dịch
          </p>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 stagger-children">
          {[
            { label: "Theo dõi", value: watchlist.length, icon: <BarChart2 size={16} /> },
            { label: "▲ Tăng", value: upCount, icon: <TrendingUp size={16} />, color: "text-[#0ecb81]" },
            { label: "▼ Giảm", value: downCount, icon: <TrendingDown size={16} />, color: "text-[#f6465d]" },
            {
              label: "Cập nhật",
              value: lastUpdate ? lastUpdate.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "--",
              icon: <Activity size={16} />,
              color: "text-[#fcd535]",
              small: true,
            },
          ].map((s, i) => (
            <div key={i} className="card-micro bg-[#1e2329] p-4 rounded-xl border border-[#2b3139] flex items-center gap-4 transition-all duration-300 cursor-default">
              <div className={cn("p-2 rounded-full bg-[#2b3139]", s.color || "text-[#707a8a]")}>{s.icon}</div>
              <div>
                <div className={cn("font-bold font-mono", s.small ? "text-[16px]" : "text-[24px]", s.color || "text-[#ffffff]")}>
                  {typeof s.value === "number" ? <CountUpValue value={s.value} /> : s.value}
                </div>
                <div className="text-[12px] text-[#707a8a]">{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 mb-6 fade-in">
          {/* Filter */}
          {(["all", "crypto", "stock"] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={cn("px-4 py-2 rounded-md text-[14px] font-semibold transition-all",
                filter === f ? "bg-[#2b3139] text-[#ffffff]" : "bg-transparent text-[#707a8a] hover:text-[#eaecef]"
              )}>
              {f === "all" ? "Tất cả" : f === "crypto" ? "Crypto" : "Cổ phiếu"}
            </button>
          ))}

          <div className="flex-1" />

          {/* Add + Refresh */}
          <button onClick={() => setShowAdd(true)}
            className="btn-primary flex items-center gap-1.5 px-4 py-2 rounded-md text-[14px] font-semibold">
            <Plus size={16} /> Thêm tài sản
          </button>
          <button
            onClick={() => fetchAll(watchlist, true)}
            disabled={refreshing}
            className="p-2.5 rounded-md bg-[#1e2329] text-[#707a8a] hover:text-[#ffffff] border border-[#2b3139] transition-colors"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
          </button>
        </div>

        {/* Live indicator */}
        {!loading && (
          <div className="flex items-center gap-2 mb-4 text-xs text-[#848e9c] fade-in">
            <span className="w-1.5 h-1.5 rounded-full bg-[#03a66d] pulse-dot" />
            Dữ liệu real-time từ yfinance · Tự động cập nhật mỗi 60 giây
            {refreshing && <span className="text-[#f0b90b]">· Đang làm mới...</span>}
          </div>
        )}

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {watchlist.slice(0, 8).map((_, i) => <div key={i} className="shimmer h-[200px] rounded-xl" />)}
          </div>
        ) : displayTickers.length === 0 ? (
          <div className="text-center py-20 fade-in">
            <BarChart2 size={48} className="mx-auto mb-4 text-[#2b3139]" />
            <p className="text-[#707a8a]">Chưa có tài sản nào trong danh sách này</p>
            <button onClick={() => setShowAdd(true)} className="mt-4 btn-primary px-4 py-2 rounded-md font-semibold">
              Thêm tài sản
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 stagger-children">
            {displayTickers.map(ticker => {
              const quote = quotes.get(ticker);
              if (!quote) {
                return (
                  <div key={ticker} className="relative group">
                    <div className="bg-[#1e2329] border border-[#2b3139] p-4 rounded-xl h-[200px]">
                      <div className="text-xs font-mono text-[#707a8a] mb-2">{ticker}</div>
                      <div className="shimmer h-8 w-24 rounded mb-2" />
                      <div className="shimmer h-4 w-16 rounded" />
                    </div>
                    <button
                      onClick={() => removeTicker(ticker)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-[#cf304a] text-white opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-10"
                    >
                      <X size={10} />
                    </button>
                  </div>
                );
              }
              return <PriceCard key={ticker} item={quote} onRemove={() => removeTicker(ticker)} />;
            })}

            {/* Add more card */}
            <button
              onClick={() => setShowAdd(true)}
              className="card-hover bg-[#1e2329] border border-dashed border-[#2b3139] p-4 rounded-xl flex flex-col items-center justify-center gap-3 text-[#707a8a] hover:text-[#fcd535] hover:border-[#fcd535] transition-all min-h-[200px]"
            >
              <div className="w-10 h-10 rounded-full bg-[#2b3139] flex items-center justify-center">
                <Plus size={20} />
              </div>
              <span className="text-[14px] font-semibold">Thêm tài sản</span>
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="mt-10 text-center text-[11px] text-[#2b3139]">
          ForecastAI V2 · Dữ liệu từ Yahoo Finance · Dự báo AI chỉ mang tính tham khảo
        </div>
      </main>
    </div>
  );
}
