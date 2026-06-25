"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { adminApi, type Portfolio } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { ArrowLeft, TrendingUp, TrendingDown, Play, Square, DollarSign, Activity, LogOut, CheckCircle, Shield } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

function cn(...c: (string | false | undefined)[]) { return c.filter(Boolean).join(" "); }

export default function AdminPage() {
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialBalance, setInitialBalance] = useState(10000);
  const [tradeForm, setTradeForm] = useState<{ ticker: string; action: "BUY" | "SELL"; quantity: number }>({ ticker: "BTC-USD", action: "BUY", quantity: 0.001 });
  const [msg, setMsg] = useState<string | null>(null);
  const [accuracyRecords, setAccuracyRecords] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);

  async function loadChart() {
    try {
      const data = await adminApi.portfolioChart();
      const formatted = data.map(d => ({
        ...d,
        timeLabel: new Date(d.time).toLocaleString("vi-VN", { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      }));
      setChartData(formatted);
    } catch (e) {
      console.error("Failed to load chart", e);
    }
  }

  async function loadAccuracy() {
    try {
      const res = await adminApi.systemAccuracy() as { success: boolean, records: any[] };
      if (res.success) setAccuracyRecords(res.records);
    } catch (e) {
      console.error("Failed to load accuracy:", e);
    }
  }

  async function loadPortfolio() {
    setLoading(true);
    setError(null);
    try {
      const p = await adminApi.portfolio();
      setPortfolio(p);
    } catch {
      setError("Không thể tải thông tin danh mục đầu tư. Hãy kiểm tra kết nối API.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    async function checkAuth() {
      // First check Supabase session
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        localStorage.setItem("forecast_ai_token", session.access_token);
        const email = session.user.email || "Google User";
        localStorage.setItem("forecast_ai_username", email);
        setUsername(email);
        loadPortfolio();
        loadAccuracy();
        loadChart();
        return;
      }

      // Fallback to custom token
      const storedToken = localStorage.getItem("forecast_ai_token");
      const storedUser = localStorage.getItem("forecast_ai_username");
      if (!storedToken) {
        router.push("/login");
      } else {
        if (storedUser) setUsername(storedUser);
        loadPortfolio();
        loadAccuracy();
        loadChart();
      }
    }
    
    checkAuth();
  }, [router]);

  async function refresh() {
    try {
      const p = await adminApi.portfolio();
      setPortfolio(p);
      loadChart();
    } catch (e: unknown) {
      console.error(e);
    }
  }

  async function toggleTrading() {
    if (!portfolio) return;
    setLoading(true);
    try {
      if (portfolio.is_running) {
        await adminApi.stopTrading();
      } else {
        await adminApi.startTrading(initialBalance);
      }
      await refresh();
      setMsg(portfolio.is_running ? "Auto-trading đã dừng" : `Bắt đầu với $${initialBalance.toLocaleString()}`);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function executeTrade() {
    setLoading(true);
    try {
      const res = await adminApi.trade(tradeForm.ticker, tradeForm.action, tradeForm.quantity) as { price?: number };
      setMsg(`✅ ${tradeForm.action} ${tradeForm.quantity} ${tradeForm.ticker} @ $${res.price?.toFixed(2)}`);
      await refresh();
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    localStorage.removeItem("forecast_ai_token");
    localStorage.removeItem("forecast_ai_username");
    await supabase.auth.signOut();
    router.push("/login");
  }

  const pnlPct = portfolio ? (portfolio.total_pnl / portfolio.initial_balance * 100) : 0;

  if (!username || !portfolio) {
    return (
      <div className="min-h-screen bg-[#0b0e11] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-[#f0b90b] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[#848e9c]">Đang tải dữ liệu...</p>
        </div>
      </div>
    );
  }

  // ── Admin Dashboard ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#0b0e11]">
      <nav className="sticky top-0 z-50 border-b border-[#1e2329] bg-[#12161c]/95 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-[#848e9c] hover:text-[#eaecef] transition-colors"><ArrowLeft size={20} /></Link>
            <span className="font-bold gradient-text text-lg">ForecastAI</span>
            <span className="text-[#2b3139]">/</span>
            <span className="text-[#eaecef] font-semibold">Admin Panel</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-[#03a66d]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#03a66d] pulse-dot" />
              Hi, {username}
            </div>
            {username === 'admin' && (
              <Link href="/superadmin" className="px-3 py-1.5 rounded-lg bg-[#fcd535] text-black font-semibold text-sm hover:bg-[#f0b90b] transition-colors flex items-center gap-1">
                <Shield size={14} /> Superadmin
              </Link>
            )}
            <button onClick={handleLogout}
              className="px-3 py-1.5 rounded-lg bg-[#1e2329] border border-[#2b3139] text-[#848e9c] text-sm hover:text-[#eaecef] transition-colors flex items-center gap-1">
              <LogOut size={14} /> Đăng xuất
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-[#eaecef]">Paper Trading Admin</h1>
          <p className="text-[#848e9c] text-sm mt-1">Theo dõi hiệu suất dự báo AI theo thời gian thực</p>
        </div>

        {error && <div className="glass border-[#cf304a]/30 p-3 rounded-lg text-[#cf304a] text-sm">{error}</div>}
        {msg && <div className="glass border-[#03a66d]/30 p-3 rounded-lg text-[#03a66d] text-sm">{msg}</div>}

        {portfolio && (
          <>
            {/* KPI Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Số dư ban đầu", value: `$${portfolio.initial_balance.toLocaleString()}`, icon: <DollarSign size={16} />, color: "text-[#848e9c]" },
                { label: "Số dư hiện tại", value: `$${portfolio.current_balance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, icon: <DollarSign size={16} />, color: "text-[#eaecef]" },
                {
                  label: "P&L", value: `${portfolio.total_pnl >= 0 ? "+" : ""}$${portfolio.total_pnl.toFixed(2)} (${pnlPct.toFixed(2)}%)`,
                  icon: portfolio.total_pnl >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />,
                  color: portfolio.total_pnl >= 0 ? "text-[#03a66d]" : "text-[#cf304a]"
                },
                { label: "Win Rate", value: `${portfolio.win_rate.toFixed(1)}% (${portfolio.win_trades}W / ${portfolio.loss_trades}L)`, icon: <Activity size={16} />, color: "text-[#f0b90b]" },
              ].map((s, i) => (
                <div key={i} className="glass p-4 rounded-xl">
                  <div className={cn("flex items-center gap-2 mb-1", s.color)}>{s.icon}<span className="text-xs text-[#848e9c]">{s.label}</span></div>
                  <div className={cn("font-bold text-sm", s.color)}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Portfolio Performance Chart */}
            {chartData.length > 0 && (
              <div className="glass p-6 rounded-xl">
                <h2 className="font-semibold text-[#eaecef] mb-4">Hiệu suất danh mục (Số dư tài khoản)</h2>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#fcd535" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#fcd535" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2b3139" vertical={false} />
                      <XAxis 
                        dataKey="timeLabel" 
                        stroke="#848e9c" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false} 
                        minTickGap={30}
                      />
                      <YAxis 
                        domain={['dataMin - 1000', 'dataMax + 1000']} 
                        stroke="#848e9c" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false}
                        tickFormatter={(val) => `$${val.toLocaleString()}`}
                      />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1e2329', borderColor: '#2b3139', color: '#eaecef' }}
                        itemStyle={{ color: '#fcd535' }}
                        formatter={(value: number) => [`$${value.toLocaleString()}`, 'Số dư']}
                        labelStyle={{ color: '#848e9c' }}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="balance" 
                        stroke="#fcd535" 
                        strokeWidth={2}
                        fillOpacity={1} 
                        fill="url(#colorBalance)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Status + Controls */}
            <div className="glass p-6 rounded-xl">
              <h2 className="font-semibold text-[#eaecef] mb-4">Auto-Trading Controls</h2>
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className={cn("w-2 h-2 rounded-full", portfolio.is_running ? "bg-[#03a66d] pulse-dot" : "bg-[#848e9c]")} />
                  <span className="text-sm text-[#b7bdc6]">
                    {portfolio.is_running ? "Auto-trading đang chạy" : "Auto-trading đã dừng"}
                  </span>
                </div>
                {!portfolio.is_running && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-[#848e9c]">Ngân sách:</span>
                    <input
                      type="number"
                      value={initialBalance}
                      onChange={e => setInitialBalance(Number(e.target.value))}
                      className="w-28 bg-[#2b3139] border border-[#2b3139] rounded px-2 py-1 text-sm text-[#eaecef] focus:outline-none focus:border-[#f0b90b]"
                    />
                    <span className="text-xs text-[#848e9c]">USD</span>
                  </div>
                )}
                <button
                  onClick={toggleTrading}
                  disabled={loading}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all",
                    portfolio.is_running
                      ? "bg-[#cf304a]/20 text-[#cf304a] hover:bg-[#cf304a]/30 border border-[#cf304a]/30"
                      : "bg-[#03a66d] text-white hover:bg-[#03a66d]/80"
                  )}
                >
                  {portfolio.is_running ? <><Square size={14} /> Dừng lại</> : <><Play size={14} /> Bắt đầu</>}
                </button>
              </div>
            </div>

            {/* Manual Trade */}
            <div className="glass p-6 rounded-xl">
              <h2 className="font-semibold text-[#eaecef] mb-4">Manual Trade</h2>
              <div className="flex flex-col sm:flex-row gap-3">
                <select
                  value={tradeForm.ticker}
                  onChange={e => setTradeForm(p => ({ ...p, ticker: e.target.value }))}
                  className="bg-[#2b3139] border border-[#2b3139] rounded-lg px-3 py-2 text-sm text-[#eaecef] focus:outline-none focus:border-[#f0b90b]"
                >
                  {["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD"].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <select
                  value={tradeForm.action}
                  onChange={e => setTradeForm(p => ({ ...p, action: e.target.value as "BUY" | "SELL" }))}
                  className="bg-[#2b3139] border border-[#2b3139] rounded-lg px-3 py-2 text-sm text-[#eaecef] focus:outline-none focus:border-[#f0b90b]"
                >
                  <option value="BUY">MUA (BUY)</option>
                  <option value="SELL">BÁN (SELL)</option>
                </select>
                <input
                  type="number"
                  step="0.001"
                  value={tradeForm.quantity}
                  onChange={e => setTradeForm(p => ({ ...p, quantity: Number(e.target.value) }))}
                  placeholder="Số lượng"
                  className="w-28 bg-[#2b3139] border border-[#2b3139] rounded-lg px-3 py-2 text-sm text-[#eaecef] focus:outline-none focus:border-[#f0b90b]"
                />
                <button
                  onClick={executeTrade}
                  disabled={loading}
                  className={cn(
                    "px-4 py-2 rounded-lg font-semibold text-sm transition-all",
                    tradeForm.action === "BUY"
                      ? "bg-[#03a66d] text-white hover:bg-[#03a66d]/80"
                      : "bg-[#cf304a] text-white hover:bg-[#cf304a]/80"
                  )}
                >
                  {loading ? "..." : `${tradeForm.action} ${tradeForm.ticker}`}
                </button>
              </div>
            </div>

            {/* Recent Trades */}
            {portfolio.recent_trades.length > 0 && (
              <div className="glass p-6 rounded-xl">
                <h2 className="font-semibold text-[#eaecef] mb-4">Lịch sử giao dịch gần đây</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[#848e9c] text-xs border-b border-[#2b3139]">
                        <th className="text-left py-2">Thời gian</th>
                        <th className="text-left py-2">Tài sản</th>
                        <th className="text-center py-2">Loại</th>
                        <th className="text-right py-2">Số lượng</th>
                        <th className="text-right py-2">Giá</th>
                        <th className="text-right py-2">Tổng</th>
                        <th className="text-center py-2">Tín hiệu</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.recent_trades.map((t: { trade_time: string, ticker: string, action: string, quantity: number, price: number, total_value: number, model_signal: string }, i) => (
                        <tr key={i} className="border-b border-[#1e2329] hover:bg-[#2b3139]/30">
                          <td className="py-2 text-[#848e9c] text-xs">{new Date(t.trade_time).toLocaleString("vi-VN")}</td>
                          <td className="py-2 font-medium text-[#eaecef]">{t.ticker}</td>
                          <td className="py-2 text-center">
                            <span className={cn("px-2 py-0.5 rounded text-xs font-bold",
                              t.action === "BUY" ? "bg-[#03a66d]/15 text-[#03a66d]" : "bg-[#cf304a]/15 text-[#cf304a]"
                            )}>{t.action}</span>
                          </td>
                          <td className="py-2 text-right text-[#b7bdc6]">{t.quantity}</td>
                          <td className="py-2 text-right text-[#b7bdc6]">${t.price?.toFixed(2)}</td>
                          <td className="py-2 text-right text-[#eaecef] font-medium">${t.total_value?.toFixed(2)}</td>
                          <td className="py-2 text-center text-xs text-[#848e9c]">{t.model_signal}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            
            {/* System Accuracy */}
            {accuracyRecords.length > 0 && (
              <div className="glass p-6 rounded-xl">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle size={18} className="text-[#03a66d]" />
                  <h2 className="font-semibold text-[#eaecef]">Độ chính xác AI (Auto-Evaluated)</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[#848e9c] text-xs border-b border-[#2b3139]">
                        <th className="text-left py-2">Ngày dự báo</th>
                        <th className="text-left py-2">Tài sản</th>
                        <th className="text-center py-2">Mô hình</th>
                        <th className="text-right py-2">Giá AI đoán</th>
                        <th className="text-right py-2">Giá thực tế</th>
                        <th className="text-right py-2">Sai số (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accuracyRecords.map((r, i) => (
                        <tr key={i} className="border-b border-[#1e2329] hover:bg-[#2b3139]/30">
                          <td className="py-2 text-[#848e9c] text-xs">{r.forecast_date}</td>
                          <td className="py-2 font-medium text-[#eaecef]">{r.ticker}</td>
                          <td className="py-2 text-center text-xs text-[#848e9c]">{r.model_name}</td>
                          <td className="py-2 text-right text-[#b7bdc6]">${r.predicted_price?.toFixed(2)}</td>
                          <td className="py-2 text-right text-[#eaecef] font-medium">${r.actual_price?.toFixed(2)}</td>
                          <td className="py-2 text-right">
                            <span className={cn("px-2 py-0.5 rounded text-xs font-bold",
                              r.error_pct < 2 ? "bg-[#03a66d]/15 text-[#03a66d]" : 
                              r.error_pct < 5 ? "bg-[#f0b90b]/15 text-[#f0b90b]" : "bg-[#cf304a]/15 text-[#cf304a]"
                            )}>{r.error_pct?.toFixed(2)}%</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
