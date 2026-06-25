"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Users, Settings, Trash2, Edit2, ShieldAlert } from "lucide-react";

export default function SuperadminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<any | null>(null);
  const [newBalance, setNewBalance] = useState<number>(0);

  useEffect(() => {
    const storedUser = localStorage.getItem("forecast_ai_username");
    if (storedUser !== "admin") {
      router.push("/admin");
      return;
    }
    loadUsers();
  }, [router]);

  async function loadUsers() {
    setLoading(true);
    try {
      const token = localStorage.getItem("forecast_ai_token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/superadmin/users`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to load users");
      const data = await res.json();
      setUsers(data.users || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveBalance() {
    if (!editingUser) return;
    try {
      const token = localStorage.getItem("forecast_ai_token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/superadmin/users/${editingUser.id}/balance`, {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ new_balance: Number(newBalance) })
      });
      if (!res.ok) throw new Error("Failed to update balance");
      setMsg(`Đã cập nhật số dư cho ${editingUser.username}`);
      setEditingUser(null);
      loadUsers();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function deleteUser(userId: number, username: string) {
    if (!confirm(`Bạn có chắc chắn muốn xóa tài khoản ${username} vĩnh viễn không?`)) return;
    try {
      const token = localStorage.getItem("forecast_ai_token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/superadmin/users/${userId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to delete user");
      setMsg(`Đã xóa tài khoản ${username}`);
      loadUsers();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0e11]">
      <nav className="sticky top-0 z-50 border-b border-[#1e2329] bg-[#12161c]/95 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <Link href="/admin" className="text-[#848e9c] hover:text-[#eaecef] transition-colors"><ArrowLeft size={20} /></Link>
          <ShieldAlert size={20} className="text-[#fcd535]" />
          <span className="font-bold text-[#eaecef] text-lg">Superadmin Control Panel</span>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {error && <div className="glass border-[#cf304a]/30 p-3 rounded-lg text-[#cf304a] text-sm">{error}</div>}
        {msg && <div className="glass border-[#03a66d]/30 p-3 rounded-lg text-[#03a66d] text-sm">{msg}</div>}

        <div className="glass p-6 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-[#eaecef] flex items-center gap-2">
              <Users size={18} /> Danh sách Người dùng
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#848e9c] text-xs border-b border-[#2b3139]">
                  <th className="text-left py-2">ID</th>
                  <th className="text-left py-2">Tên đăng nhập</th>
                  <th className="text-left py-2">Ngày đăng ký</th>
                  <th className="text-right py-2">Số dư (USD)</th>
                  <th className="text-right py-2">Lợi nhuận (P&L)</th>
                  <th className="text-center py-2">Auto-Trade</th>
                  <th className="text-right py-2">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="text-center py-4 text-[#848e9c]">Đang tải...</td></tr>
                ) : users.map(u => (
                  <tr key={u.id} className="border-b border-[#1e2329] hover:bg-[#2b3139]/30">
                    <td className="py-2 text-[#848e9c]">{u.id}</td>
                    <td className="py-2 font-medium text-[#eaecef]">{u.username}</td>
                    <td className="py-2 text-[#848e9c] text-xs">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="py-2 text-right">
                      {editingUser?.id === u.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <input 
                            type="number" 
                            className="w-24 bg-[#0b0e11] border border-[#f0b90b] rounded px-2 py-1 text-right text-[#eaecef]"
                            value={newBalance}
                            onChange={(e) => setNewBalance(Number(e.target.value))}
                          />
                          <button onClick={saveBalance} className="text-xs bg-[#03a66d] text-white px-2 py-1 rounded">Lưu</button>
                          <button onClick={() => setEditingUser(null)} className="text-xs bg-[#2b3139] text-[#eaecef] px-2 py-1 rounded">Hủy</button>
                        </div>
                      ) : (
                        <span className="text-[#eaecef] font-medium">${u.balance.toFixed(2)}</span>
                      )}
                    </td>
                    <td className="py-2 text-right">
                      <span className={u.pnl >= 0 ? "text-[#03a66d]" : "text-[#cf304a]"}>
                        {u.pnl >= 0 ? "+" : ""}${u.pnl.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs ${u.is_running ? "bg-[#03a66d]/20 text-[#03a66d]" : "bg-[#2b3139] text-[#848e9c]"}`}>
                        {u.is_running ? "Đang chạy" : "Tắt"}
                      </span>
                    </td>
                    <td className="py-2 flex justify-end gap-2">
                      <button 
                        onClick={() => { setEditingUser(u); setNewBalance(u.balance); }}
                        className="p-1.5 rounded bg-[#2b3139] text-[#eaecef] hover:bg-[#fcd535] hover:text-black transition-colors"
                        title="Sửa số dư"
                      >
                        <Edit2 size={14} />
                      </button>
                      {u.username !== "admin" && (
                        <button 
                          onClick={() => deleteUser(u.id, u.username)}
                          className="p-1.5 rounded bg-[#cf304a]/20 text-[#cf304a] hover:bg-[#cf304a] hover:text-white transition-colors"
                          title="Xóa tài khoản"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
