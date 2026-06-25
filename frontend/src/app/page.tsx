"use client"

import { useEffect, useState, useRef } from "react"
import Link from "next/link"
import { ArrowUpRight, Sparkles, TrendingDown, TrendingUp, Search, Plus, Trash2, Loader2, LogIn } from "lucide-react"
import { AVAILABLE_TICKERS } from "@/lib/forecast-data"
import { marketApi, authApi, type LiveQuote, type TickerSearchResult } from "@/lib/api"

export default function Page() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({})
  const [loading, setLoading] = useState(true)
  
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<TickerSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  
  const searchTimer = useRef<NodeJS.Timeout | null>(null)

  // 1. Initial Load: Check Auth & Fetch Watchlist
  useEffect(() => {
    const token = localStorage.getItem("forecast_ai_token")
    if (token) {
      setIsLoggedIn(true)
      authApi.getWatchlist().then(res => {
        if (res.success && res.watchlist.length > 0) {
          setWatchlist(res.watchlist)
        } else {
          setWatchlist(AVAILABLE_TICKERS) // Fallback if empty
        }
      }).catch(() => {
        setWatchlist(AVAILABLE_TICKERS)
      })
    } else {
      setWatchlist(AVAILABLE_TICKERS)
    }
  }, [])

  // 2. Fetch Live Quotes when Watchlist changes
  useEffect(() => {
    if (watchlist.length === 0) {
      setLoading(false);
      return;
    }
    
    let active = true;
    const fetchQuotes = async () => {
      try {
        const res = await marketApi.overview(watchlist)
        if (!active) return;
        const qMap: Record<string, LiveQuote> = {}
        res.data.forEach(q => qMap[q.ticker] = q)
        setQuotes(qMap)
      } catch (err) {
        console.error("Failed to fetch quotes", err)
      } finally {
        if (active) setLoading(false)
      }
    }
    
    fetchQuotes()
    
    // Auto-refresh every 60s
    const interval = setInterval(fetchQuotes, 60000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [watchlist])

  // 3. Search Logic
  const handleSearchInput = (v: string) => {
    setSearchQuery(v)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!v.trim()) {
      setSearchResults([])
      return
    }
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await marketApi.search(v)
        setSearchResults(res.results)
      } catch (e) {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 400)
  }

  // 4. Add/Remove Watchlist
  const handleAdd = async (ticker: string) => {
    if (!isLoggedIn) return;
    if (watchlist.includes(ticker)) {
      setShowSearch(false);
      setSearchQuery("");
      setSearchResults([]);
      return;
    }
    
    try {
      await authApi.addWatchlist(ticker)
      setWatchlist(prev => [...prev, ticker])
      setShowSearch(false)
      setSearchQuery("")
      setSearchResults([])
    } catch (e) {
      alert("Failed to add to watchlist")
    }
  }

  const handleRemove = async (e: React.MouseEvent, ticker: string) => {
    e.preventDefault() // prevent navigating to forecast link
    if (!isLoggedIn) return;
    try {
      await authApi.removeWatchlist(ticker)
      setWatchlist(prev => prev.filter(t => t !== ticker))
    } catch (e) {
      alert("Failed to remove from watchlist")
    }
  }

  return (
    <main className="min-h-screen relative">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-16">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-primary">
            <Sparkles className="size-4" />
            AI Forecast Engine
          </div>
          {!isLoggedIn && (
            <Link href="/login" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors bg-card border border-border px-3 py-1.5 rounded-lg">
              <LogIn size={16} /> Đăng nhập
            </Link>
          )}
        </div>
        
        <h1 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight text-balance sm:text-5xl">
          Price forecasts with confidence bands and automated research
        </h1>
        <p className="mt-4 max-w-xl text-pretty leading-relaxed text-muted-foreground">
          Pick an asset to view its AI-projected price path, forecast
          candlesticks, and a full research breakdown. Adjust the forecast
          horizon from 1 to 60 days.
        </p>

        <div className="mt-12 flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Watchlist của bạn</h2>
          {isLoggedIn ? (
            <button 
              onClick={() => setShowSearch(!showSearch)}
              className="flex items-center gap-2 text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Plus size={16} /> Thêm mã
            </button>
          ) : (
            <span className="text-sm text-muted-foreground bg-secondary/50 px-3 py-1 rounded-full border border-border/50">
              Đăng nhập để tùy biến watchlist
            </span>
          )}
        </div>

        {/* Search Dialog Inline */}
        {showSearch && isLoggedIn && (
          <div className="mb-8 bg-card border border-border rounded-xl p-4 fade-in">
            <div className="relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                autoFocus
                value={searchQuery}
                onChange={e => handleSearchInput(e.target.value)}
                placeholder="Tìm mã giao dịch (VD: BTC-USD, AAPL...)"
                className="w-full bg-background border border-border rounded-lg pl-10 pr-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
              />
              {searching && <Loader2 size={16} className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />}
            </div>
            
            {searchResults.length > 0 && (
              <div className="mt-2 border border-border rounded-lg overflow-hidden bg-background">
                {searchResults.map(r => (
                  <button 
                    key={r.symbol}
                    onClick={() => handleAdd(r.symbol)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted transition-colors border-b border-border last:border-0 text-left"
                  >
                    <div>
                      <span className="font-mono font-bold text-foreground">{r.symbol}</span>
                      <span className="text-muted-foreground text-sm ml-3">{r.name}</span>
                    </div>
                    <span className="text-xs bg-card px-2 py-1 rounded border border-border text-muted-foreground">{r.exchange}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[1,2,3,4,5,6].map(i => <div key={i} className="shimmer h-32 rounded-xl" />)}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {watchlist.map((ticker) => {
              const q = quotes[ticker]
              if (!q) return null // loading or failed
              const up = q.change_pct >= 0
              
              const decimals = q.price >= 1000 ? 0 : 2
              const priceStr = `$${q.price.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`

              return (
                <Link
                  key={ticker}
                  href={`/forecast/${ticker}`}
                  className="group relative rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 font-mono text-xs font-bold text-primary">
                        {ticker.slice(0, 3)}
                      </div>
                      <div>
                        <p className="font-semibold">{ticker}</p>
                        <p className="text-xs text-muted-foreground line-clamp-1 max-w-[120px]">
                          {q.name || ticker}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {isLoggedIn && (
                        <button 
                          onClick={(e) => handleRemove(e, ticker)}
                          className="p-1.5 text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10 rounded-md transition-colors opacity-0 group-hover:opacity-100"
                          title="Xóa khỏi watchlist"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                      <ArrowUpRight className="size-4 text-muted-foreground transition-colors group-hover:text-primary" />
                    </div>
                  </div>

                  <div className="mt-4 flex items-end justify-between">
                    <span className="font-mono text-lg font-semibold tabular-nums">
                      {priceStr}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 text-sm font-medium tabular-nums ${
                        up ? "text-up" : "text-down"
                      }`}
                    >
                      {up ? (
                        <TrendingUp className="size-4" />
                      ) : (
                        <TrendingDown className="size-4" />
                      )}
                      {up ? "+" : ""}
                      {q.change_pct.toFixed(2)}%
                    </span>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}
