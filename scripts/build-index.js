const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const distDir = path.join(root, 'dist');

// clean dist
if (fs.existsSync(distDir)) fs.rmSync(distDir, { recursive: true });
fs.mkdirSync(distDir, { recursive: true });

// 1. scan skills
const skillDirs = fs.readdirSync(root, { withFileTypes: true })
  .filter(d => d.isDirectory() && !d.name.startsWith('.') && d.name !== 'scripts')
  .map(d => d.name);

const skills = [];

for (const dir of skillDirs) {
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

// 2. write index.json
fs.writeFileSync(path.join(distDir, 'index.json'), JSON.stringify(skills, null, 2) + '\n');

// 3. copy skill directories to dist/
for (const dir of skillDirs) {
  const src = path.join(root, dir);
  if (!fs.existsSync(path.join(src, 'SKILL.md'))) continue;
  const dst = path.join(distDir, dir);
  fs.mkdirSync(dst, { recursive: true });
  for (const file of fs.readdirSync(src)) {
    fs.copyFileSync(path.join(src, file), path.join(dst, file));
  }
}

// 4. copy api directory to dist/
const apiSrc = path.join(root, 'api');
if (fs.existsSync(apiSrc)) {
  const apiDst = path.join(distDir, 'api');
  fs.mkdirSync(apiDst, { recursive: true });
  for (const file of fs.readdirSync(apiSrc)) {
    fs.copyFileSync(path.join(apiSrc, file), path.join(apiDst, file));
  }
}

// 5. copy public/ files to dist/
const publicDir = path.join(root, 'public');
if (fs.existsSync(publicDir)) {
  for (const file of fs.readdirSync(publicDir)) {
    const src = path.join(publicDir, file);
    const dst = path.join(distDir, file);
    if (fs.statSync(src).isDirectory()) {
      fs.mkdirSync(dst, { recursive: true });
      for (const f of fs.readdirSync(src)) {
        fs.copyFileSync(path.join(src, f), path.join(dst, f));
      }
    } else {
      fs.copyFileSync(src, dst);
    }
  }
}

console.log(`Built ${skills.length} skills to dist/`);
skills.forEach(s => console.log(`  ${s.name}: ${s.url}`));
