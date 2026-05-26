# My Skills

WorkBuddy Skills 托管仓库。通过 URL 直接访问 SKILL.md：

```
https://<your-domain>/slurm/SKILL.md
https://<your-domain>/weather/SKILL.md
```

## 结构

```
skill-name/
  SKILL.md       ← 技能定义文件
  ...            ← 其他资源（可选）
```

## 部署

推送到 GitHub，在 Vercel 中导入即可。每个 skill 目录会自动映射为路径。

## 技能加密

支持对 Skills 正文进行 AES-256-GCM 加密，用户只能看到元数据（名称、描述），正文需通过 AI 助手解密后使用。

### 原理

```
SkillHub 存储加密 .dat → 用户看到乱码 → MCP 解密 → AI 拿到明文
```

- **元数据明文**：名称、描述等 frontmatter 不加密，方便浏览发现
- **正文加密**：AES-256-GCM，nonce(12) + ciphertext + tag(16)
- **MCP 纯解密**：`skill_decrypt_mcp.py` 只提供 `decrypt_base64` 一个工具，密钥来自环境变量

### 配置文件

`encrypted-skills.json` — 加密白名单，JSON 对象，key 为目录名：

```json
{"daily-report": true, "weekly-report": true}
```

### 命令

```bash
# 本地生成加密文件
npm run encrypt

# 构建时自动执行（Vercel 部署时也会跑）
npm run build
```

### 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `SKILL_ENCRYPTION_KEY` | AES-256 密钥（64 位 hex） | 加密时必填 |
| `ADMIN_PASSWORD` | Admin 登录密码 | 必填 |
| `ADMIN_JWT_SECRET` | JWT 签名密钥 | 必填 |

`.env.local`（本地开发）：

```
ADMIN_PASSWORD=skills2026
ADMIN_JWT_SECRET=<your-secret>
SKILL_ENCRYPTION_KEY=<64-char-hex-key>
```

Vercel 部署时需在 Dashboard → Settings → Environment Variables 中设置同样三个变量。

### MCP 配置

`~/.workbuddy/mcp.json`：

```json
{
  "mcpServers": {
    "skill-decrypt": {
      "command": "python",
      "args": ["path/to/skill_decrypt_mcp.py"],
      "env": {
        "SKILL_ENCRYPTION_KEY": "<same-key>"
      }
    }
  }
}
```

### 使用流程

1. 在 `encrypted-skills.json` 中添加要加密的技能目录名
2. 本地运行 `npm run encrypt` 生成 `public/encrypted/*.dat`
3. 推送代码 → Vercel 自动构建（prebuild 阶段加密）
4. 首页列表中加密技能显示 🔒
5. 点击进入详情页可看到元数据，正文被隐藏
6. AI 助手通过 MCP `decrypt_base64` 解密正文到内存
