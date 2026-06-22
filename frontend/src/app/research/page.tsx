"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, Newspaper, Brain, ArrowLeft, Loader2 } from "lucide-react";
import { marketApi, type TickerSearchResult } from "@/lib/api";

const POPULAR = [
  { symbol: "BTC-USD", name: "Bitcoin" },
  { symbol: "ETH-USD", name: "Ethereum" },
  { symbol: "SOL-USD", name: "Solana" },
  { symbol: "BNB-USD", name: "BNB" },
  { symbol: "DOGE-USD", name: "Dogecoin" },
  { symbol: "AVAX-USD", name: "Avalanche" },
];

export default function ResearchIndexPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function doSearch(q: string) {
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const res = await marketApi.search(q);
      setResults(res.results);
    } catch { setResults([]); }
    finally { setSearching(false); }
  }

  function handleInput(v: string) {
    setQuery(v);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => doSearch(v), 400);
  }

  function navigateTo(ticker: string) {
    router.push(`/research/${ticker.toUpperCase()}`);
  }

  return (
    <div className="min-h-screen bg-[#0b0e11]">
      <nav className="sticky top-0 z-40 border-b border-[#1e2329] bg-[#12161c]/95 backdrop-blur-md">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <Link href="/" className="text-[#848e9c] hover:text-[#eaecef] transition-colors"><ArrowLeft size={20} /></Link>
          <span className="font-bold gradient-text text-lg">ForecastAI</span>
          <span className="text-[#2b3139]">/</span>
          <span className="text-[#eaecef]">Research</span>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 py-12">
        {/* Hero */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 rounded-2xl bg-[#f0b90b]/10 flex items-center justify-center mx-auto mb-4">
            <Newspaper size={28} className="text-[#f0b90b]" />
          </div>
          <h1 className="text-3xl font-bold gradient-text mb-2">AI Market Research</h1>
          <p className="text-[#848e9c]">
            Gemini AI phân tích tin tức + sentiment cho bất kỳ mã giao dịch nào
          </p>
        </div>

        {/* Search */}
        <div className="relative mb-8">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#848e9c]" />
          <input
            value={query}
            onChange={e => handleInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && query && navigateTo(query)}
            placeholder="Nhập mã: BTC-USD, ETH-USD, DOGE-USD, FPT.VN..."
            className="w-full bg-[#1e2329] border border-[#2b3139] rounded-xl pl-12 pr-12 py-4 text-[#eaecef] placeholder-[#848e9c] focus:outline-none focus:border-[#f0b90b] transition-colors text-lg"
          />
          {searching
            ? <Loader2 size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-[#848e9c] animate-spin" />
            : query && (
              <button onClick={() => navigateTo(query)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-[#f0b90b] text-[#12161c] px-3 py-1.5 rounded-lg text-sm font-semibold hover:bg-[#f8d12f] transition-colors">
                Phân tích
              </button>
            )
          }
        </div>

        {/* Search results */}
        {results.length > 0 && (
          <div className="glass rounded-xl mb-6 overflow-hidden">
            {results.map(r => (
              <button key={r.symbol} onClick={() => navigateTo(r.symbol)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#2b3139] transition-colors border-b border-[#1e2329] last:border-0 text-left">
                <Brain size={16} className="text-[#f0b90b] flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <span className="font-mono font-semibold text-[#eaecef]">{r.symbol}</span>
                  <span className="text-[#848e9c] text-sm ml-2">{r.name}</span>
                </div>
                <span className="text-[10px] text-[#848e9c] bg-[#1e2329] px-1.5 py-0.5 rounded">{r.exchange}</span>
              </button>
            ))}
          </div>
        )}

        {/* Popular picks */}
        <div>
          <div className="text-xs text-[#848e9c] font-medium mb-3 uppercase tracking-wider">Phổ biến</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {POPULAR.map(p => (
              <Link key={p.symbol} href={`/research/${p.symbol}`}
                className="glass p-4 rounded-xl flex items-center gap-3 hover:border-[#f0b90b]/30 transition-all group">
                <div className="w-8 h-8 rounded-lg bg-[#f0b90b]/10 flex items-center justify-center flex-shrink-0">
                  <TrendingUp size={14} className="text-[#f0b90b]" />
                </div>
                <div className="min-w-0">
                  <div className="font-mono font-semibold text-[#eaecef] text-sm group-hover:text-[#f0b90b] transition-colors">{p.symbol}</div>
                  <div className="text-[10px] text-[#848e9c]">{p.name}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
