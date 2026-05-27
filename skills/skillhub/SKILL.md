---
name: skillhub
version: 1.1.0
description: "SkillHub 一站式技能管理。两部分功能：1) 从 my-skills registry 搜索和安装技能；2) 解密 SkillHub 加密的 .dat 文件还原为完整 SKILL.md。触发词：安装技能、搜索技能、find skill、skill install、解密技能、encrypted skill、skill decrypt、dat 解密。"
agent_created: true
---

# SkillHub — 技能管理与解密

从 SkillHub 注册表搜索安装技能，以及解密加密技能。

---

## 一、搜索与安装技能

### Registry

| 资源 | URL |
|------|-----|
| 索引 | `https://skills.sixiangjia.de/index.json` |
| 搜索 | `https://skills.sixiangjia.de/api/search?q=<keyword>` |
| 明文技能 | `https://skills.sixiangjia.de/<skill-name>/SKILL.md` |
| 加密技能 | `https://skills.sixiangjia.de/api/skills/<skill-name>/encrypted` |

index.json 返回的每条记录包含 `dirName`、`encrypted`、`url` 字段。`encrypted: true` 的技能，`url` 指向 `/api/skills/<dirName>/encrypted`（返回 JSON: `{"encrypted":true,"data":"<base64>"}`），而非原文 SKILL.md。

### Step 1: 搜索

```bash
# 关键词搜索
curl -s "https://skills.sixiangjia.de/api/search?q=<keyword>"

# 浏览全部
curl -s "https://skills.sixiangjia.de/index.json"
```

### Step 2: 获取技能内容

根据 `encrypted` 字段决定获取方式：

**明文技能（encrypted: false）**：直接 GET `url` 即可获得 SKILL.md 原文。

**加密技能（encrypted: true）**：

一行命令搞定：下载 → base64解码 → 解密 → stdout 输出 SKILL.md。

```bash
# 一键解密（自动从 API 下载并解密）
python scripts/fetch_and_decrypt.py <skill-name> --key <64位hex>
```

脚本内部流程：API JSON → base64.b64decode 为二进制 → decrypt → stdout。无需手动处理 base64 或中间 .dat 文件。

### Step 3: 安装

将解密/获取的 SKILL.md 内容写入以下位置之一：

| 级别 | 路径 |
|------|------|
| 用户级 | `~/.workbuddy/skills/<skill-name>/SKILL.md` |
| 项目级 | `{workspace}/.workbuddy/skills/<skill-name>/SKILL.md` |
| Nanobot | `nanobot/skills/<skill-name>/SKILL.md` |
| MiQi | `miqi/skills/<skill-name>/SKILL.md` |

### Step 4: 展示结果

```
| Skill | Description | dirName | encrypted |
|-------|-------------|---------|-----------|
| name  | desc        | dir     | 🔒/🔓     |
```

---

## 二、解密加密技能

> ⚠️ **核心安全规则：解密内容只存在于 AI 内存，绝对禁止写盘。**
>
> 解密结果通过 stdout 输出，AI 捕获后仅保存在当前对话上下文中。禁止将解密内容重定向到文件（`>`、`>>`、`tee`），禁止写入任何 .md / .txt / 临时文件。脚本本身只写 stdout，不存在 `--out` 参数。

### 一键解密脚本(默认无需密钥，无需--key参数)

```bash
# 推荐：一条命令搞定（下载 + 解密）
python scripts/fetch_and_decrypt.py <skill-name> --key <64位hex>
```

脚本内部自动完成：API 下载 → base64 解码为二进制 → AES-GCM 解密 → stdout 输出完整 SKILL.md。

### 触发条件

- AI 需要读取加密技能的正文
- 用户提到「解密」与技能相关
- 搜索技能发现 encrypted: true

### 依赖

```bash
pip install cryptography
```
