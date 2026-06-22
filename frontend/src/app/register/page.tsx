"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { UserPlus, ArrowLeft, Loader2, TrendingUp, Eye, EyeOff, Shield } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("forecast_ai_token")) {
      router.push("/admin");
    }
  }, [router]);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.register(username, password);
      localStorage.setItem("forecast_ai_token", res.token);
      localStorage.setItem("forecast_ai_username", res.username);
      router.push("/admin");
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message || "Đăng ký thất bại");
      else setError("Đăng ký thất bại");
    } finally {
      setLoading(false);
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
          <h1 className="text-2xl font-bold text-[#eaecef]">Đăng Ký Tài Khoản</h1>
          <p className="text-sm text-[#848e9c] mt-2">Tạo tài khoản để trải nghiệm hệ thống giao dịch AI</p>
        </div>

        {/* Card */}
        <div className="bg-[#1e2329] p-8 rounded-2xl border border-[#2b3139] shadow-2xl shadow-black/20">
          {error && (
            <div className="bg-[#cf304a]/10 border border-[#cf304a]/30 text-[#cf304a] text-sm px-4 py-3 rounded-lg mb-6 flex items-center gap-2 fade-in">
              <Shield size={14} />
              {error}
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-5">
            {/* Username — Floating Label */}
            <div className="float-input-group">
              <input
                type="text"
                id="reg-username"
                placeholder=" "
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-xl px-4 py-4 pt-6 pb-2 text-[#eaecef] placeholder-transparent focus:outline-none focus:border-[#fcd535] transition-all duration-300"
                required
              />
              <label htmlFor="reg-username">Tên đăng nhập (tối thiểu 3 ký tự)</label>
            </div>

            {/* Password — Floating Label */}
            <div className="float-input-group relative">
              <input
                type={showPassword ? "text" : "password"}
                id="reg-password"
                placeholder=" "
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-xl px-4 py-4 pt-6 pb-2 pr-12 text-[#eaecef] placeholder-transparent focus:outline-none focus:border-[#fcd535] transition-all duration-300"
                required
              />
              <label htmlFor="reg-password">Mật khẩu (tối thiểu 4 ký tự)</label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-[#707a8a] hover:text-[#ffffff] transition-colors"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Confirm Password — Floating Label */}
            <div className="float-input-group">
              <input
                type={showPassword ? "text" : "password"}
                id="reg-confirm"
                placeholder=" "
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-[#0b0e11] border border-[#2b3139] rounded-xl px-4 py-4 pt-6 pb-2 text-[#eaecef] placeholder-transparent focus:outline-none focus:border-[#fcd535] transition-all duration-300"
                required
              />
              <label htmlFor="reg-confirm">Xác nhận mật khẩu</label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !username || !password || !confirmPassword}
              className="btn-primary w-full py-3.5 rounded-xl text-[15px] font-bold disabled:opacity-50 flex items-center justify-center gap-2 transition-all duration-300"
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Đang đăng ký...
                </>
              ) : (
                <>
                  <UserPlus size={16} /> Đăng ký tài khoản
                </>
              )}
            </button>
          </form>

          {/* Login link */}
          <div className="mt-6 pt-6 border-t border-[#2b3139] text-center">
            <p className="text-sm text-[#848e9c]">
              Đã có tài khoản?{" "}
              <Link href="/login" className="text-[#fcd535] hover:underline font-semibold nav-link">
                Đăng nhập
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
