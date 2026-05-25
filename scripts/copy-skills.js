const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PUBLIC = path.join(ROOT, 'public');

// Skill directories to copy from (skip app_data, scripts, .git, etc.)
const SKILL_DIRS = [
  'daily-new-record',
  'daily-report',
  'find-install-skills',
  'kaggle-notebook-rules',
  'slurm',
  'weekly-report',
  'work-ledger',
  'wsl-sandbox',
];

console.log('Copying SKILL.md files to public/...');

for (const dir of SKILL_DIRS) {
  const src = path.join(ROOT, dir, 'SKILL.md');
  const destDir = path.join(PUBLIC, dir);
  const dest = path.join(destDir, 'SKILL.md');

  if (!fs.existsSync(src)) {
    console.log(`  SKIP ${dir} — no SKILL.md found`);
    continue;
  }

  fs.mkdirSync(destDir, { recursive: true });
  fs.copyFileSync(src, dest);
  console.log(`  OK   ${dir}/SKILL.md`);
}

console.log('Done.');
