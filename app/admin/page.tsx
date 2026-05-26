'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';

export default function AdminLoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/admin/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        const { token } = await res.json();
        Cookies.set('admin_token', token, { expires: 1 });
        router.push('/admin/dashboard');
      } else {
        setError('密码错误');
      }
    } catch {
      setError('请求失败，请重试');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-[#111] border border-[#1a1a1a] rounded-lg p-8 space-y-5"
      >
        <h1 className="text-xl font-semibold text-center">My Skills Admin</h1>
        <p className="text-[#555] text-xs text-center">输入管理员密码以继续</p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full bg-[#0d0d0d] border border-[#1a1a1a] rounded-md px-3 py-2 text-sm text-[#e0e0e0] placeholder:text-[#333] focus:outline-none focus:border-[#333]"
          autoFocus
        />

        {error && <p className="text-red-500 text-xs">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full bg-[#e0e0e0] text-[#0a0a0a] rounded-md py-2 text-sm font-medium hover:bg-white disabled:opacity-40 transition-colors"
        >
          {loading ? '验证中...' : '登录'}
        </button>
      </form>
    </div>
  );
}
