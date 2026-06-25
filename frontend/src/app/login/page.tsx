"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { LogIn, ArrowLeft, Loader2, TrendingUp, Eye, EyeOff, Shield } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("forecast_ai_token")) {
      router.push("/admin");
    }
  }, [router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.login(username, password);
      localStorage.setItem("forecast_ai_token", res.token);
      localStorage.setItem("forecast_ai_username", res.username);
      router.push("/admin");
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message || "Đăng nhập thất bại");
      else setError("Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  async function handleGoogleLogin() {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/admin`
        }
      });
      if (error) throw error;
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message || "Đăng nhập Google thất bại");
      else setError("Đăng nhập Google thất bại");
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0e11] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Decorative ambient glow */}
      <div className="absolute top-[-20%] left-[-15%] w-[55%] h-[55%] rounded-full bg-[#f0b90b]/[0.03] blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-15%] w-[55%] h-[55%] rounded-full bg-[#03a66d]/[0.03] blur-[150px] pointer-events-none" />

      {/* Top bar */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-[64px] flex items-center">
          <Link href="/" className="flex items-center gap-2 text-[#707a8a] hover:text-[#ffffff] transition-colors">
            <ArrowLeft size={18} />
            <span className="text-sm font-medium">Về Dashboard</span>
          </Link>
        </div>
      </div>

      <div className="w-full max-w-[420px] relative z-10 fade-in-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-10 h-10 flex items-center justify-center text-[#fcd535]">
              <TrendingUp size={28} />
            </div>
            <span className="font-bold text-[28px] text-[#fcd535] tracking-[-0.5px]">BINANCE<span className="text-[#ffffff] font-normal"> AI</span></span>
          </div>
          <h1 className="text-2xl font-bold text-[#eaecef]">Đăng Nhập</h1>
          <p className="text-sm text-[#848e9c] mt-2">Truy cập vào hệ thống giao dịch tự động AI</p>
        </div>

        {/* Card */}
        <div className="bg-[#1e2329] p-8 rounded-2xl border border-[#2b3139] shadow-2xl shadow-black/20">
          {error && (
            <div className="bg-[#cf304a]/10 border border-[#cf304a]/30 text-[#cf304a] text-sm px-4 py-3 rounded-lg mb-6 flex items-center gap-2 fade-in">
              <Shield size={14} />
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            {/* Username — Floating Label */}
            <div className="float-input-group">
              <input
                type="text"
                id="username"
                placeholder=" "
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-xl px-4 py-4 pt-6 pb-2 text-[#eaecef] placeholder-transparent focus:outline-none focus:border-[#fcd535] transition-all duration-300"
                required
              />
              <label htmlFor="username">Tên đăng nhập</label>
            </div>

            {/* Password — Floating Label + Show/Hide */}
            <div className="float-input-group relative">
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                placeholder=" "
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-xl px-4 py-4 pt-6 pb-2 pr-12 text-[#eaecef] placeholder-transparent focus:outline-none focus:border-[#fcd535] transition-all duration-300"
                required
              />
              <label htmlFor="password">Mật khẩu</label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-[#707a8a] hover:text-[#ffffff] transition-colors"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !username || !password}
              className="btn-primary w-full py-3.5 rounded-xl text-[15px] font-bold disabled:opacity-50 flex items-center justify-center gap-2 transition-all duration-300"
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Đang xử lý...
                </>
              ) : (
                <>
                  <LogIn size={16} /> Đăng nhập
                </>
              )}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#2b3139]"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-[#1e2329] text-[#707a8a]">Hoặc</span>
            </div>
          </div>

          <button
            onClick={handleGoogleLogin}
            type="button"
            className="w-full py-3.5 bg-white text-black rounded-xl text-[15px] font-bold flex items-center justify-center gap-2 hover:bg-gray-100 transition-colors"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Đăng nhập bằng Google
          </button>

          {/* Register link */}
          <div className="mt-6 pt-6 border-t border-[#2b3139] text-center">
            <p className="text-sm text-[#848e9c]">
              Chưa có tài khoản?{" "}
              <Link href="/register" className="text-[#fcd535] hover:underline font-semibold nav-link">
                Đăng ký ngay
              </Link>
            </p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[11px] text-[#2b3139] mt-6">
          ForecastAI V2 · Bảo mật end-to-end
        </p>
      </div>
    </div>
  );
}
