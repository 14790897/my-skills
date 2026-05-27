---
name: skillhub
version: 1.2.0
description: "SkillHub 一站式技能管理。从 my-skills registry 搜索和安装技能（明文/加密）。加密技能支持本地安装（保存 .dat + 元数据），使用时解密。触发词：安装技能、搜索技能、find skill、skill install、解密技能、encrypted skill、skill decrypt。"
agent_created: true
---

# SkillHub — 技能管理与解密

从 SkillHub 注册表搜索、安装技能，以及解密加密技能。

---

## 一、搜索技能

```bash
# 关键词搜索
curl -s "https://skills.sixiangjia.de/api/search?q=<keyword>"

# 浏览全部
curl -s "https://skills.sixiangjia.de/index.json"
```

index.json 每条记录包含 `dirName`、`encrypted`、`url` 字段。

---

## 二、安装技能

### 明文技能（encrypted: false）

直接 GET `url` 获取 SKILL.md 原文，写入安装路径即可。

### 加密技能（encrypted: true）

使用 `--install` 一键安装：下载 .dat + 提取元数据写 SKILL.md。

```bash
python scripts/fetch_and_decrypt.py <skill-name> --install --skills-root ~/.workbuddy/skills
```

**安装效果：**
- `~/.workbuddy/skills/<skill-name>/skill.dat` — 加密二进制文件
- `~/.workbuddy/skills/<skill-name>/SKILL.md` — 元数据（frontmatter 含 name/description/version/encrypted 标记）+ 使用说明

AI 读到 SKILL.md 的元数据即可知道技能做什么，无需解密。

### 安装路径

| 级别 | 路径 |
|------|------|
| 用户级 | `~/.workbuddy/skills/<skill-name>/` |
| 项目级 | `{workspace}/.workbuddy/skills/<skill-name>/` |
| Nanobot | `nanobot/skills/<skill-name>/SKILL.md` |
| MiQi | `miqi/skills/<skill-name>/SKILL.md` |
---

## 三、使用加密技能

加密技能安装后，SKILL.md 只含元数据。需要完整内容时，运行解密命令：

```bash
# 解密本地已安装的加密技能 → stdout
python scripts/fetch_and_decrypt.py <skill-name> --local --skills-root ~/.workbuddy/skills
```

密钥由环境变量自动注入，AI 无需关心。

### 安全规则

> ⚠️ **解密内容只存在于 AI 内存，绝对禁止写盘。**
>
> 解密结果通过 stdout 输出，AI 捕获后仅保存在当前对话上下文中。禁止将解密内容重定向到文件（`>`、`>>`、`tee`），禁止用 Write 工具写盘。

### 一键模式（不安装，直接下载解密）

如果不想本地安装，也可以一次性下载 + 解密：

```bash
python scripts/fetch_and_decrypt.py <skill-name>
```

---

## 四、脚本参考

`scripts/fetch_and_decrypt.py` 三种模式：

| 模式 | 命令 | 说明 |
|------|------|------|
| 安装 | `--install --skills-root <dir>` | 下载 .dat + 提取元数据 SKILL.md（不解密） |
| 本地解密 | `--local --skills-root <dir>` | 解密本地已安装的 .dat → stdout |
| 一键解密 | _(无额外参数)_ | 下载 + 解密 → stdout（不保存本地） |

> `--skills-root` 是必填参数，指定技能安装目录。用户级传 `~/.workbuddy/skills`，项目级传 `{workspace}/.workbuddy/skills`。

### 依赖

```bash
pip install cryptography
```

---

## 五、展示搜索结果

```
| Skill | Description | dirName | encrypted |
|-------|-------------|---------|-----------|
| name  | desc        | dir     | 🔒/🔓     |
```
