---
name: miqroprobe-github-flow
slug: miqroprobe-github-flow
version: 1.0.0
description: |
  公司项目（前端/后端双仓库）在 GitHub 上的个人协作工作流：以固定 base 分支切 feature 分支、
  一变更一 issue 一 PR、PR 描述 7 节模板、E2E 独立 test/e2e-* 分支与 PR、gh CLI 用法、
  提交前验证命令（tsc/build、JBR + wrapper Maven）。GitHub 只是个人 issue/PR 工作区，
  公司合并仍走公司 GitLab MR。
  Triggers: "给项目提PR", "frontend PR", "backend PR", "GitHub issue", "开 issue",
  "提 PR", "GitHub skills", "前后端各提一个 PR".
agent_created: true
---

# 公司项目 GitHub 工作流（个人工作区）

## 仓库与分支模型

| 项 | 约定 |
|---|---|
| 前端 | `<org>/<frontend-repo>`（本地仓库目录自定） |
| 后端 | `<org>/<backend-repo>`（本地仓库目录自定） |
| Base 分支 | `origin/<base-branch>`（团队集成分支，如 `v2.3-agent`；**不要**直接推它） |
| Feature 分支 | `feat/<slug>`、`fix/<slug>`，从 `origin/<base-branch>` 切 |
| E2E 分支 | `test/e2e-<slug>`，独立分支/PR，**绝不混入功能分支** |
| 远端 | `origin` = GitHub（个人工作区），`gitlab` = 公司仓库；公司合并一律走 MR |

用户红线：GitHub 只用于个人 issue/PR；公司可见的合并走公司 GitLab MR；GitHub 的 PR 描述里
不要引用公司内网无法访问的链接（反向：GitLab MR 不引用 GitHub 链接）。

## Issue（每个 PR 配一个）

仓库通常没有 `.github` 模板，`gh issue create --title ... --body ...` 手写即可。正文必填节：

```markdown
## 类型
- [x] ✨ 新功能

## 变更概述
一句话 + 3~5 条要点

## 背景/问题
为什么要做、现状缺什么

## 验收标准
可验证的 2~4 条
```

## 分支与提交

```bash
git fetch origin
git checkout -b feat/<slug> origin/<base-branch>
# ...开发...
git add <具体文件>          # 不要 git add -A，避免带进无关改动
git commit -m "feat(scope): 中文摘要"     # Conventional Commits，scope 如 agent/assistant
git push -u origin feat/<slug>            # 注意：-u 会把 upstream 设到新分支，别推错
```

提交信息末尾补（本仓库习惯）：

```text
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

## PR（描述用 7 节模板）

```bash
gh pr create -R <org>/<repo> --base <base-branch> --head feat/<slug> \
  --title "feat(scope): ..." --body "$(cat <<'EOF'
## 类型
- [x] ✨ 新功能
Closes #<issue>

## 变更概述
## 背景/问题
## 变更内容
- 文件/模块级别逐条

## 日志/验证证据
```text
$ ./node_modules/.bin/tsc --noEmit   → exit 0
$ npm run build                      → ✓ built in XXs
$ mvn -q -DskipTests compile         → EXIT=0
```

## 测试情况
## 本地 E2E
## 截图

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

要求：

- 标题 `<type>(<scope>): 中文摘要`，type 只用 feat / fix / perf / refactor / docs / style / test / build / ci / chore / revert
- 一个 PR 只做一件事；E2E 另开 PR
- 有 E2E 结果就把「18/18」之类的断言清单贴进「本地 E2E」节
- PR 已开但后续有修复提交：`gh pr edit <n> --body ...` 更新描述里的验证证据

## 提交前验证（必做）

前端：

```bash
./node_modules/.bin/tsc --noEmit       # 类型检查
npm run build                          # 生产构建
```

⚠️ 若 `vite.config.ts` 里 `visualizer({ open: true })`，构建结束会**打开 stats.html**——
用户明确不允许打开。构建前临时 `sed -i 's/open: true/open: false/' vite.config.ts`，
构建后 `git checkout -- vite.config.ts` 还原，别提交这个改动。

后端（无系统 java/mvn 时用 JBR + wrapper Maven）：

```bash
export JAVA_HOME="<JBR 路径，如 C:/Program Files/Android/Android Studio/jbr>"
MVN="<maven wrapper 缓存路径>/bin/mvn"
sh "$MVN" -q -DskipTests compile        # 或 package 出 jar
```

## E2E 约定（独立分支）

- 分支：`test/e2e-<slug>`，基于对应功能分支（保证可直接跑），PR 也只含 e2e 文件
- 目录：`e2e/`，至少包含：用例脚本 `*.mjs`、造数脚本、`README.md`（前置条件 + 运行命令 + 最近结果）
- 写法（本机惯例）：headless Chrome + CDP WebSocket（`Runtime.evaluate` / `Input.insertText` /
  `Page.captureScreenshot`），**API 断言 + UI 断言两段**，每步 `step(name, ok)` 输出
- 需要真实模型时用本地栈：Docker（MySQL / Redis / Mongo 容器）+ 后端 jar
  （按项目 profile 启动，Windows 上常需 `-Djdk.net.unixdomain.tmpdir=C:/temp`）
  + 前端 dev server（vite 代理临时指向本地后端，不提交）+ 环境变量里的模型 Key
- 测试后清理：停 dev server / 后端 jar / 容器，删临时脚本，截图归档到工作目录

## gh 常用

```bash
gh auth status
gh issue create -R <org>/<repo> ...
gh pr create -R <org>/<repo> --base <base-branch> --head <branch> ...
gh pr view <n> -R <org>/<repo> --json title,body
gh pr edit <n> -R <org>/<repo> --body ...
gh pr list -R <org>/<repo> --state merged --limit 5
```

## 常见坑

- `git checkout -b ... origin/<base-branch>` 会自动把 upstream 指到 `origin/<base-branch>`，
  push 时必须 `git push -u origin <新分支>`，否则会尝试推 base 分支
- 纯新增文件的 cherry-pick 一般干净；跨分支合并大文件（如 canvas/状态机组件）容易产生「两份
  代码拼接」的假合并，合完先 tsc + build 再信
- 不要把 E2E 提交进功能分支或公司 GitLab；公司侧只交功能 MR
- 给同事看的链接只能是公司内可见的（GitLab），GitHub 链接别写进公司 MR
