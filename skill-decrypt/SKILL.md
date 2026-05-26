---
name: skill-decrypt
version: 1.0.0
description: "解密 SkillHub 加密技能。AI 直接运行 scripts/decrypt.py 将 .dat 密文还原为完整 SKILL.md。支持文件路径、base64 字符串、stdin 三种输入方式。触发词：解密技能、encrypted skill、skill decrypt、dat 解密。"
agent_created: true
---

# Skill Decrypt — 加密技能解密

直接调用 `scripts/decrypt.py` 解密 SkillHub 加密的 `.dat` 文件，输出完整 `SKILL.md`。

## 触发条件

- AI 需要读取加密技能的正文
- 从 SkillHub API 获取到 base64 密文
- 用户提到「解密」与技能相关

## 使用方式

### 1. 传入 .dat 文件路径

```bash
python scripts/decrypt.py <path-to>.dat --key <64位hex密钥>
```

### 2. 传入 base64 字符串

```bash
python scripts/decrypt.py --b64 "<base64密文>" --key <64位hex密钥>
```

### 3. 从 stdin 读取

```bash
cat <path-to>.dat | python scripts/decrypt.py --key <64位hex密钥>
```

### 4. 通过环境变量传密钥（避免命令行暴露）

```bash
export SKILL_ENCRYPTION_KEY=<64位hex密钥>
python scripts/decrypt.py <path-to>.dat
```

## AI 执行流程

```
1. 获取密文（文件路径 / base64 / 从 API 拉取）
2. 运行 scripts/decrypt.py 解密
3. 拿到完整 SKILL.md（含 frontmatter + 正文）
4. 正文仅存在于 AI 上下文，不落盘
```

## 依赖

```bash
pip install cryptography
```

## 安全

- 密钥可通过环境变量注入，不暴露在命令行
- 解密结果输出到 stdout，AI 捕获后使用，不写文件
