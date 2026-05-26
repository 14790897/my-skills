import { notFound } from 'next/navigation';
import Link from 'next/link';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';
import matter from 'gray-matter';
import MarkdownBody from '@/components/markdown-body';
import type { Metadata } from 'next';

interface SkillPageProps {
  params: Promise<{ skill: string }>;
}

// Known skill directories - pre-computed to avoid fs scanning in worker threads
const SKILL_DIRS = [
  'daily-new-record',
  'daily-report',
  'find-install-skills',
  'kaggle-notebook-rules',
  'slurm',
  'weekly-report',
  'work-ledger',
  'workbuddy-find-skills',
  'wsl-sandbox',
];

function readSkill(dirName: string): { frontmatter: Record<string, unknown>; body: string } | null {
  const filePath = resolve(process.cwd(), dirName, 'SKILL.md');
  if (!existsSync(filePath)) return null;
  const raw = readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  return { frontmatter: data, body: content };
}

function isEncrypted(dirName: string): boolean {
  const configPath = resolve(process.cwd(), 'encrypted-skills.json');
  if (!existsSync(configPath)) return false;
  try {
    const config = JSON.parse(readFileSync(configPath, 'utf-8'));
    return !!config[dirName];
  } catch {
    return false;
  }
}

export async function generateStaticParams() {
  return SKILL_DIRS.map((dir) => ({ skill: dir }));
}

export async function generateMetadata({ params }: SkillPageProps): Promise<Metadata> {
  const { skill } = await params;
  const content = readSkill(skill);
  if (!content) return { title: 'Not Found' };
  return {
    title: `${content.frontmatter.name || skill} - My Skills`,
    description: (content.frontmatter.description as string) || '',
  };
}

export default async function SkillPage({ params }: SkillPageProps) {
  const { skill } = await params;
  const content = readSkill(skill);

  if (!content) {
    notFound();
  }

  const name = (content.frontmatter.name as string) || skill;
  const description = (content.frontmatter.description as string) || '';
  const skillUrl = `/${skill}/SKILL.md`;
  const encrypted = isEncrypted(skill);

  return (
    <main className="max-w-[720px] mx-auto px-6 py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-[#888] hover:text-[#ccc] transition-colors mb-6"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M9 3L5 7l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Back to all skills
      </Link>

      <div className="flex items-center gap-2.5 mb-4 py-2.5 px-3.5 bg-[#111] border border-[#1a1a1a] rounded-md">
        <span className="font-mono text-sm text-[#ccc] flex-1">
          {encrypted && <span className="mr-1.5 text-[#666]">&#x1f512;</span>}
          {name}
        </span>
        <a
          href={skillUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-[#666] font-mono hover:text-[#aaa] transition-colors"
        >
          SKILL.md ↗
        </a>
      </div>

      {description && (
        <p className="text-[#888] text-sm mb-6">{description}</p>
      )}

      {encrypted ? (
        <div className="border border-dashed border-[#1a1a1a] rounded-lg p-6 text-center">
          <p className="text-[#555] text-xs">此技能正文已加密，需通过 AI 助手使用</p>
        </div>
      ) : (
        <MarkdownBody content={content.body} />
      )}

      <footer className="mt-12 pt-6 border-t border-[#1a1a1a] text-[#444] text-xs flex justify-between flex-wrap gap-2">
        <Link href="/index.json" className="text-[#555] hover:text-[#888] transition-colors">
          index.json
        </Link>
        <span>Powered by Vercel</span>
      </footer>
    </main>
  );
}
