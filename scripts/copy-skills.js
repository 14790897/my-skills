const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const SKILLS_DIR = path.join(ROOT, 'skills');
const PUBLIC = path.join(ROOT, 'public');

// Skill directories to copy from (skip app_data, scripts, .git, etc.)
const SKILL_DIRS = [
  "daily-new-record",
  "daily-report",
  "kaggle-notebook-rules",
  "skillhub",
  "slurm",
  "weekly-report",
  "work-ledger",
  "wsl-sandbox",
];

// ── Encryption helpers ─────────────────────────────────────────────

function encryptBody(body, keyHex) {
  const key = Buffer.from(keyHex, 'hex');
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, nonce);
  const encrypted = Buffer.concat([cipher.update(body), cipher.final()]);
  const tag = cipher.getAuthTag();
  // Returns: nonce(12) + encrypted + tag(16)
  return Buffer.concat([nonce, encrypted, tag]);
}

function getEncryptedSkills() {
  const configPath = path.join(SKILLS_DIR, 'encrypted-skills.json');
  if (!fs.existsSync(configPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch {
    return {};
  }
}

function parseFrontmatter(text) {
  // Simple YAML frontmatter parser (avoids extra dependency)
  const match = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!match) return { metadata: {}, body: text };
  const yaml = match[1];
  const body = match[2];
  const metadata = {};
  for (const line of yaml.split('\n')) {
    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim();
    const value = line.slice(colonIdx + 1).trim();
    if (key) metadata[key] = value;
  }
  return { metadata, body };
}

// ── Main ────────────────────────────────────────────────────────────

console.log('Copying SKILL.md files to public/...');

const keyHex = process.env.SKILL_ENCRYPTION_KEY || '';
const encryptedSkills = getEncryptedSkills();
const encryptDir = path.join(PUBLIC, 'encrypted');

if (keyHex) {
  fs.mkdirSync(encryptDir, { recursive: true });
}

for (const dir of SKILL_DIRS) {
  const src = path.join(SKILLS_DIR, dir, 'SKILL.md');

  if (!fs.existsSync(src)) {
    console.log(`  SKIP ${dir} — no SKILL.md found`);
    continue;
  }

  const isEncrypted = keyHex && encryptedSkills[dir];

  if (isEncrypted) {
    // Encrypted skills: only output .dat, NO plaintext SKILL.md in public/
    const text = fs.readFileSync(src, 'utf-8');
    const { metadata, body } = parseFrontmatter(text);
    const metaJson = Buffer.from(JSON.stringify(metadata), 'utf-8');
    const metaLen = Buffer.alloc(4);
    metaLen.writeUInt32LE(metaJson.length, 0);
    const encryptedBody = encryptBody(Buffer.from(body, 'utf-8'), keyHex);

    const dat = Buffer.concat([metaLen, metaJson, encryptedBody]);
    const datPath = path.join(encryptDir, `${dir}.dat`);
    fs.writeFileSync(datPath, dat);
    console.log(`  ENC  ${dir} → encrypted/${dir}.dat (meta=${metaJson.length}B, body_cipher=${encryptedBody.length}B)`);
  } else {
    // Non-encrypted skills: copy plaintext SKILL.md to public/
    const destDir = path.join(PUBLIC, dir);
    const dest = path.join(destDir, 'SKILL.md');
    fs.mkdirSync(destDir, { recursive: true });
    fs.copyFileSync(src, dest);
    console.log(`  OK   ${dir}/SKILL.md`);
  }
}

console.log('Done.');
