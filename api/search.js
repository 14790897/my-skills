const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  const query = (req.query.q || '').toLowerCase().trim();

  if (!query) {
    res.status(400).json({ error: 'Missing query parameter: q' });
    return;
  }

  const root = path.resolve(__dirname, '..');
  const dirs = fs.readdirSync(root, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith('.') && d.name !== 'public' && d.name !== 'scripts' && d.name !== 'api')
    .map(d => d.name);

  const results = [];

  for (const dir of dirs) {
    const skillFile = path.join(root, dir, 'SKILL.md');
    if (!fs.existsSync(skillFile)) continue;

    const content = fs.readFileSync(skillFile, 'utf-8').replace(/\r\n/g, '\n');

    // parse frontmatter
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    const frontmatter = {};
    if (match) {
      match[1].split('\n').forEach(line => {
        const [key, ...rest] = line.split(': ');
        if (key && rest.length) frontmatter[key.trim()] = rest.join(': ').trim();
      });
    }

    const name = (frontmatter.name || dir).toLowerCase();
    const desc = (frontmatter.description || '').toLowerCase();
    const body = content.toLowerCase();

    // search in name, description, and full content
    const score =
      (name.includes(query) ? 3 : 0) +
      (desc.includes(query) ? 2 : 0) +
      (body.includes(query) ? 1 : 0);

    if (score > 0) {
      results.push({
        name: frontmatter.name || dir,
        description: frontmatter.description || '',
        url: `/${dir}/SKILL.md`,
        score,
      });
    }
  }

  results.sort((a, b) => b.score - a.score);

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.status(200).json({
    query,
    count: results.length,
    results,
  });
};
