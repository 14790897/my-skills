import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { verifyAdmin, unauthorized } from '@/lib/admin-auth';

const ROOT = path.resolve(process.cwd(), 'skills');

function getSkillDirs(): string[] {
  return fs.readdirSync(ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith('.'))
    .map(d => d.name);
}

// GET /api/admin/skills/[dir] — read skill content
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ dir: string }> }
) {
  if (!await verifyAdmin(req)) return unauthorized();

  const { dir } = await params;
  const skillFile = path.join(ROOT, dir, 'SKILL.md');
  if (!fs.existsSync(skillFile)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const raw = fs.readFileSync(skillFile, 'utf-8');
  const { data, content } = matter(raw);

  return NextResponse.json({ frontmatter: data, body: content, raw });
}

// PUT /api/admin/skills/[dir] — update skill via GitHub API
export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ dir: string }> }
) {
  if (!await verifyAdmin(req)) return unauthorized();

  const { dir } = await params;
  const { body } = await req.json();

  if (!body || typeof body !== 'string') {
    return NextResponse.json({ error: 'Invalid body' }, { status: 400 });
  }

  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_REPO = process.env.GITHUB_REPO;

  if (!GITHUB_TOKEN || !GITHUB_REPO) {
    // In dev mode without GitHub: write locally
    const skillFile = path.join(ROOT, dir, 'SKILL.md');
    fs.writeFileSync(skillFile, body, 'utf-8');
    return NextResponse.json({ ok: true, mode: 'local' });
  }

  // Get current file SHA
  const filePath = `skills/${dir}/SKILL.md`;
  const ref = process.env.GITHUB_BRANCH || 'main';

  const getRes = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/contents/${filePath}?ref=${ref}`,
    { headers: { Authorization: `token ${GITHUB_TOKEN}` } }
  );

  if (!getRes.ok) {
    return NextResponse.json({ error: 'Failed to read file from GitHub' }, { status: 500 });
  }

  const fileData = await getRes.json();

  // Commit updated content
  const contentB64 = Buffer.from(body).toString('base64');

  const commitRes = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/contents/${filePath}`,
    {
      method: 'PUT',
      headers: {
        Authorization: `token ${GITHUB_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: `Update ${dir}/SKILL.md via admin`,
        content: contentB64,
        sha: fileData.sha,
        branch: ref,
      }),
    }
  );

  if (!commitRes.ok) {
    const err = await commitRes.json();
    return NextResponse.json({ error: err.message || 'GitHub commit failed' }, { status: 500 });
  }

  return NextResponse.json({ ok: true, mode: 'github' });
}
