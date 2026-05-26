import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { verifyAdminServer } from '@/lib/admin-auth-server';

// Server-side helper to read encrypted skills config
function getEncryptedSkills(): Record<string, boolean> {
  const fs = require('fs');
  const path = require('path');
  const configPath = path.join(process.cwd(), 'encrypted-skills.json');
  if (!fs.existsSync(configPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch {
    return {};
  }
}

export default async function AdminDashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token')?.value;

  if (!token || !(await verifyAdminServer(token))) {
    redirect('/admin');
  }

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

  const encryptedSkills = getEncryptedSkills();

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
        {dirs.map((dir: string) => {
          const isEnc = !!encryptedSkills[dir];
          return (
            <div
              key={dir}
              className="flex items-center justify-between bg-[#111] border border-[#1a1a1a] rounded-md px-4 py-3 group"
            >
              <Link
                href={`/admin/skills/${dir}/edit`}
                className="flex items-center gap-2.5 flex-1"
              >
                <span className="text-sm font-mono text-[#e0e0e0] group-hover:text-white transition-colors">
                  {dir}
                </span>
              </Link>
              <div className="flex items-center gap-2">
                {/* Encryption toggle */}
                <form action={`/api/admin/skills/${dir}/encrypt`} method="POST">
                  <button
                    type="submit"
                    title={isEnc ? 'Disable encryption' : 'Enable encryption'}
                    className={`text-sm px-2 py-0.5 rounded transition-colors ${
                      isEnc
                        ? 'bg-[#1a3a1a] text-[#4ade80] hover:bg-[#1a2a1a]'
                        : 'bg-[#1a1a1a] text-[#555] hover:bg-[#222]'
                    }`}
                  >
                    {isEnc ? '\u{1f512}' : '\u{1f513}'}
                  </button>
                </form>
                {/* Edit button */}
                <Link
                  href={`/admin/skills/${dir}/edit`}
                  className="text-[#333] text-xs hover:text-[#555] transition-colors"
                >
                  Edit →
                </Link>
              </div>
            </div>
          );
        })}
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
