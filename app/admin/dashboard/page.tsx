import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { verifyAdminServer } from '@/lib/admin-auth-server';

export default async function AdminDashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token')?.value;

  if (!token || !(await verifyAdminServer(token))) {
    redirect('/admin');
  }

  // Read all skill directory names (server-side)
  const fs = require('fs');
  const path = require('path');
  const ROOT = process.cwd();

  const SKIP = new Set([
    '.git','.next','.vscode','.workbuddy',
    'api','app','app_data','components','dist','lib','node_modules','public','scripts',
  ]);

  const dirs = fs.readdirSync(ROOT, { withFileTypes: true })
    .filter((d: { isDirectory(): boolean; name: string }) =>
      d.isDirectory() && !d.name.startsWith('.') && !SKIP.has(d.name)
    )
    .map((d: { name: string }) => d.name);

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-xl font-semibold">Skill Management</h1>
        <form action="/api/admin/logout" method="POST">
          <button
            type="submit"
            className="text-[#555] text-xs hover:text-[#e0e0e0] transition-colors"
          >
            Logout
          </button>
        </form>
      </div>

      <p className="text-[#555] text-xs mb-6">
        {dirs.length} skill(s) found
      </p>

      <div className="space-y-2">
        {dirs.map((dir: string) => (
          <Link
            key={dir}
            href={`/admin/skills/${dir}/edit`}
            className="flex items-center justify-between bg-[#111] border border-[#1a1a1a] rounded-md px-4 py-3 hover:border-[#333] transition-colors group"
          >
            <span className="text-sm font-mono text-[#e0e0e0]">{dir}</span>
            <span className="text-[#333] text-xs group-hover:text-[#555] transition-colors">
              Edit →
            </span>
          </Link>
        ))}
      </div>

      <div className="mt-8 pt-6 border-t border-[#1a1a1a]">
        <Link
          href="/"
          className="text-[#555] text-xs hover:text-[#888] transition-colors"
        >
          ← Back to site
        </Link>
      </div>
    </div>
  );
}
