import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

export interface SkillMeta {
  name: string;
  description: string;
  url: string;
  encrypted: boolean;
}

export interface SkillContent {
  frontmatter: Record<string, unknown>;
  body: string;
}

const ROOT = path.resolve(/* turbopackIgnore: true */ process.cwd());

const SKIP_DIRS = new Set([
  '.git',
  '.next',
  '.vscode',
  '.workbuddy',
  'api',
  'app',
  'app_data',
  'components',
  'dist',
  'lib',
  'node_modules',
  'public',
  'scripts',
]);

function getEncryptedSkills(): Record<string, boolean> {
  const configPath = path.join(ROOT, 'encrypted-skills.json');
  if (!fs.existsSync(configPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch {
    return {};
  }
}

export function getAllSkills(): SkillMeta[] {
  const encryptedSkills = getEncryptedSkills();
  const dirs = fs.readdirSync(ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith('.') && !SKIP_DIRS.has(d.name))
    .map(d => d.name);

  const skills: SkillMeta[] = [];

  for (const dir of dirs) {
    const skillFile = path.join(ROOT, dir, 'SKILL.md');
    if (!fs.existsSync(skillFile)) continue;

    const raw = fs.readFileSync(skillFile, 'utf-8');
    const { data } = matter(raw);

    skills.push({
      name: (data.name as string) || dir,
      description: (data.description as string) || '',
      url: `/${dir}/SKILL.md`,
      encrypted: !!encryptedSkills[dir],
    });
  }

  return skills;
}

export function getSkillContent(name: string): SkillContent | null {
  for (const dir of fs.readdirSync(ROOT, { withFileTypes: true })) {
    if (!dir.isDirectory() || dir.name.startsWith('.') || SKIP_DIRS.has(dir.name)) continue;
    const skillFile = path.join(ROOT, dir.name, 'SKILL.md');
    if (!fs.existsSync(skillFile)) continue;
    const raw = fs.readFileSync(skillFile, 'utf-8');
    const { data } = matter(raw);
    if ((data.name as string) === name) {
      return { frontmatter: data, body: matter(raw).content };
    }
  }
  return null;
}

export function getSkillByDir(dirName: string): SkillContent | null {
  const skillFile = path.join(ROOT, dirName, 'SKILL.md');
  if (!fs.existsSync(skillFile)) return null;
  const raw = fs.readFileSync(skillFile, 'utf-8');
  const { data, content } = matter(raw);
  return { frontmatter: data, body: content };
}

export function searchSkills(query: string): (SkillMeta & { score: number })[] {
  const encryptedSkills = getEncryptedSkills();
  const q = query.toLowerCase().trim();
  const dirs = fs.readdirSync(ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith('.') && !SKIP_DIRS.has(d.name))
    .map(d => d.name);

  const results: (SkillMeta & { score: number })[] = [];

  for (const dir of dirs) {
    const skillFile = path.join(ROOT, dir, 'SKILL.md');
    if (!fs.existsSync(skillFile)) continue;

    const raw = fs.readFileSync(skillFile, 'utf-8');
    const { data, content } = matter(raw);

    const name = ((data.name as string) || dir).toLowerCase();
    const desc = ((data.description as string) || '').toLowerCase();
    const body = content.toLowerCase();

    const score =
      (name.includes(q) ? 3 : 0) +
      (desc.includes(q) ? 2 : 0) +
      (body.includes(q) ? 1 : 0);

    if (score > 0) {
      results.push({
        name: (data.name as string) || dir,
        description: (data.description as string) || '',
        url: `/${dir}/SKILL.md`,
        encrypted: !!encryptedSkills[dir],
        score,
      });
    }
  }

  results.sort((a, b) => b.score - a.score);
  return results;
}
