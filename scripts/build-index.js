const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'public');

// ensure public dir
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

// 1. scan skills and generate index.json
const dirs = fs.readdirSync(root, { withFileTypes: true })
  .filter(d => d.isDirectory() && !d.name.startsWith('.') && d.name !== 'public' && d.name !== 'scripts')
  .map(d => d.name);

const skills = [];

for (const dir of dirs) {
  const skillFile = path.join(root, dir, 'SKILL.md');
  if (!fs.existsSync(skillFile)) continue;

  const content = fs.readFileSync(skillFile, 'utf-8').replace(/\r\n/g, '\n');
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) continue;

  const frontmatter = {};
  match[1].split('\n').forEach(line => {
    const [key, ...rest] = line.split(': ');
    if (key && rest.length) frontmatter[key.trim()] = rest.join(': ').trim();
  });

  skills.push({
    name: frontmatter.name || dir,
    description: frontmatter.description || '',
    url: `/${dir}/SKILL.md`,
  });
}

fs.writeFileSync(path.join(outDir, 'index.json'), JSON.stringify(skills, null, 2) + '\n');

// 2. copy all skill directories to public/
for (const dir of dirs) {
  const src = path.join(root, dir);
  const dst = path.join(outDir, dir);
  if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });

  for (const file of fs.readdirSync(src)) {
    fs.copyFileSync(path.join(src, file), path.join(dst, file));
  }
}

console.log(`Built ${skills.length} skills to public/`);
skills.forEach(s => console.log(`  ${s.name}: ${s.url}`));
