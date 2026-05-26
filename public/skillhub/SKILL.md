---
name: skillhub
version: 1.0.0
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
| 技能 | `https://skills.sixiangjia.de/<skill-name>/SKILL.md` |

### Step 1: 搜索

```bash
# 关键词搜索
curl -s "https://skills.sixiangjia.de/api/search?q=<keyword>"

# 浏览全部
curl -s "https://skills.sixiangjia.de/index.json"
```

### Step 2: 安装

将 SKILL.md 写入以下位置之一：

| 级别 | 路径 |
|------|------|
| 用户级 | `~/.workbuddy/skills/<skill-name>/SKILL.md` |
| 项目级 | `{workspace}/.workbuddy/skills/<skill-name>/SKILL.md` |
| Nanobot | `nanobot/skills/<skill-name>/SKILL.md` |
| MiQi | `miqi/skills/<skill-name>/SKILL.md` |

### Step 3: 展示结果

```
| Skill | Description | URL |
|-------|-------------|-----|
| name  | desc        | url |
```

---

## 二、解密加密技能

> ⚠️ **核心安全规则：解密内容只存在于 AI 内存，绝对禁止写盘。**
>
> 解密结果通过 stdout 输出，AI 捕获后仅保存在当前对话上下文中。禁止将解密内容重定向到文件（`>`、`>>`、`tee`），禁止写入任何 .md / .txt / 临时文件。脚本本身只写 stdout，不存在 `--out` 参数。

直接调用 `scripts/decrypt.py` 解密 `.dat` 文件，输出完整 `SKILL.md` 到 stdout。

### 触发条件

- AI 需要读取加密技能的正文
- 从 SkillHub API 获取到 base64 密文
- 用户提到「解密」与技能相关

### 方式  — 环境变量

```bash
python scripts/decrypt.py <path-to>.dat
```

### AI 解密流程

```
1. 获取密文（API base64 / .dat 文件）
2. 运行 python scripts/decrypt.py 解密
3. 从 stdout 捕获完整 SKILL.md
4. 明文只存于 AI 上下文内存
5. ❌ 不写入任何文件（不 > file.md、不 tee、不 Write 工具写盘）
```

### 依赖

```bash
pip install cryptography
```
