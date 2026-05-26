import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { verifyAdminServer } from '@/lib/admin-auth-server';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve } from 'path';

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ dir: string }> }
) {
  const { dir } = await params;

  // Auth check
  const cookieStore = await cookies();
  const token = cookieStore.get('admin_token')?.value;
  if (!token || !(await verifyAdminServer(token))) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Security: prevent path traversal
  if (dir.includes('..') || dir.includes('/') || dir.includes('\\')) {
    return NextResponse.json({ error: 'Invalid directory name' }, { status: 400 });
  }

  const configPath = resolve(process.cwd(), "skills", "encrypted-skills.json");
  let config: Record<string, boolean> = {};

  if (existsSync(configPath)) {
    try {
      config = JSON.parse(readFileSync(configPath, 'utf-8'));
    } catch {
      config = {};
    }
  }

  // Toggle encryption status
  const current = config[dir] || false;
  config[dir] = !current;

  writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n', 'utf-8');

  // Try to commit via GitHub API
  const githubToken = process.env.GITHUB_TOKEN;
  const githubRepo = process.env.GITHUB_REPOSITORY || "14790897/my-skills-hub";

  let commitResult = 'skipped (no GITHUB_TOKEN)';

  if (githubToken) {
    try {
      const content = Buffer.from(
        JSON.stringify(config, null, 2) + '\n'
      ).toString('base64');

      // Get current file SHA
      const getRes = await fetch(
        `https://api.github.com/repos/${githubRepo}/contents/skills/encrypted-skills.json`,
        {
          headers: {
            Authorization: `token ${githubToken}`,
            Accept: "application/vnd.github.v3+json",
          },
        },
      );

      const getData = await getRes.json();
      const sha = getData.sha;

      const putRes = await fetch(
        `https://api.github.com/repos/${githubRepo}/contents/skills/encrypted-skills.json`,
        {
          method: "PUT",
          headers: {
            Authorization: `token ${githubToken}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: `${config[dir] ? "Enable" : "Disable"} encryption for ${dir}`,
            content,
            sha,
          }),
        },
      );

      if (putRes.ok) {
        commitResult = 'committed';
      } else {
        const errData = await putRes.json();
        commitResult = `failed: ${(errData as { message?: string }).message || 'unknown'}`;
      }
    } catch (e) {
      commitResult = `error: ${e}`;
    }
  }

  return NextResponse.json({
    encrypted: config[dir],
    message: `Encryption ${config[dir] ? 'enabled' : 'disabled'} for ${dir}`,
    commit: commitResult,
  });
}
