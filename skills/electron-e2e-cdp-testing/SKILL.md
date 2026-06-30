---
name: electron-e2e-cdp-testing
description: "Electron 34+ 桌面应用端到端测试技能。当需要为 Electron 应用编写或调试 E2E 测试、遇到 Playwright _electron.launch 不可用、CI 中 Chromium SIGTRAP 崩溃、ELECTRON_RUN_AS_NODE 导致 Electron 以 Node 模式运行、或需要 CDP 远程调试连接方案时使用此技能。涵盖 CDP 连接、进程管理、跨平台 kill、CI sandbox 处理、concurrency 策略。适用于 Electron 34 及以上版本。"
agent_created: true
---

# Electron E2E CDP 测试

## 概述

Electron 34+ 移除了 `--remote-debugging-port` CLI 标志支持，导致 Playwright 的 `_electron.launch()` 不可用。本技能提供基于 CDP（Chrome DevTools Protocol）的完整测试方案，包括本地运行、CI 集成和常见坑点排查。

## 何时使用

- 为 Electron 34+ 桌面应用编写 E2E 测试
- `_electron.launch()` 报错或 Electron 启动后立即退出
- CI 中 Electron 测试出现 SIGTRAP / sandbox 崩溃
- 需要在 CI 中运行真实 Electron 的完整 E2E 测试

## 核心方案：CDP 连接替代 _electron.launch()

### 原理

| 旧方案（Electron 33 及以下） | 新方案（Electron 34+） |
|------------------------------|------------------------|
| Playwright 传 `--remote-debugging-port` CLI 标志 | `app.commandLine.appendSwitch()` + `chromium.connectOverCDP()` |
| `_electron.launch()` 一键启动 | 手动 spawn Electron binary + CDP 连接 |

### 实施步骤

#### 1. 主进程添加 CDP 端口开关

在 `src/main/index.ts` 的 `main()` 函数最开头（`app.whenReady()` 之前）添加：

```typescript
export function main(): void {
  // 必须在 app.whenReady() 之前调用 —— Chromium 初始化时读取此 switch
  if (process.env.E2E_TEST) {
    app.commandLine.appendSwitch('remote-debugging-port', '8315')
  }
  app.whenReady().then(() => {
    // ...
  })
}
```

**关键**: 用环境变量控制，生产构建不受影响。

#### 2. 测试文件中 spawn Electron + CDP 连接

```typescript
import { test, expect, chromium } from '@playwright/test'
import { spawn, execSync, type ChildProcess } from 'node:child_process'
import { resolve } from 'node:path'

const CDP_PORT = 8315
const CDP_URL = `http://localhost:${CDP_PORT}`
const BOOT_TIMEOUT = 90_000

const ELECTRON_BIN = require('electron') as string

// 等待 CDP 端点可用
async function waitForCDP(timeout = 60_000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try {
      const res = await fetch(`${CDP_URL}/json/version`, {
        signal: AbortSignal.timeout(2000),
      })
      if (res.ok) return
    } catch { /* 未就绪 */ }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`CDP endpoint at ${CDP_URL} not available within ${timeout}ms`)
}

// 跨平台杀进程树
function killProcessTree(proc: ChildProcess): void {
  if (!proc || proc.killed) return
  const pid = proc.pid
  if (!pid) return
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' })
    } else {
      proc.kill('SIGTERM')
      setTimeout(() => { try { proc.kill('SIGKILL') } catch {} }, 3000)
    }
  } catch {
    try { proc.kill('SIGKILL') } catch {}
  }
}

test.beforeAll(async () => {
  // ⚠️ 关键 1：删除 ELECTRON_RUN_AS_NODE（见坑点 1）
  const env = { ...process.env, E2E_TEST: '1' }
  delete env.ELECTRON_RUN_AS_NODE

  // ⚠️ 关键 2：CI 环境必须传 --no-sandbox 等参数（见坑点 2）
  const electronArgs = ['.', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']

  proc = spawn(ELECTRON_BIN, electronArgs, {
    cwd: APP_DIR,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  proc.stdout?.on('data', (d) => process.stdout.write(`[electron:out] ${d}`))
  proc.stderr?.on('data', (d) => process.stderr.write(`[electron:err] ${d}`))

  await waitForCDP(BOOT_TIMEOUT)

  browser = await chromium.connectOverCDP(CDP_URL)
  const context = browser.contexts()[0]
  page = context.pages()[0] || (await context.newPage())
}, BOOT_TIMEOUT + 60000)

test.afterAll(async () => {
  await browser?.close().catch(() => {})
  if (proc) killProcessTree(proc)
})
```

## 3 大通用坑点

### 坑 1: `ELECTRON_RUN_AS_NODE=1` 环境变量继承

**症状**: Electron 启动后立即退出（exit code=0），CDP 端点永不可用，无 Chromium 窗口。

**根因**: VSCode、WorkBuddy 等 Electron IDE 会在宿主环境中设置 `ELECTRON_RUN_AS_NODE=1`。子进程通过 `spawn({ env: { ...process.env } })` 继承此变量后，Electron 以纯 Node.js 模式运行，完全绕过 Chromium runtime，因此不会开启 CDP 端口。

**修复**:
```typescript
const env = { ...process.env, E2E_TEST: '1' }
delete env.ELECTRON_RUN_AS_NODE  // 必须 delete，不能设为 '0' 或 ''
```

### 坑 2: CI Chromium SIGTRAP 崩溃

**症状**: CI 日志显示 `The SUID sandbox helper binary was found, but is not configured correctly`，进程以 SIGTRAP 退出。本地运行正常，仅 CI 失败。

**根因**: GitHub Actions Ubuntu runner 以 root 用户运行。Chromium 的 sandbox 需要 setuid helper binary（`chrome-sandbox`）具有 mode 4755 且 owned by root，但 npm 安装的 Electron 中此 binary 权限不正确。

**修复**: spawn 时传 CLI 参数（**不能用 `appendSwitch`**）：
```typescript
const electronArgs = ['.', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
proc = spawn(ELECTRON_BIN, electronArgs, { ... })
```

**关键**: `--no-sandbox` 必须作为 CLI 参数传递。`app.commandLine.appendSwitch('no-sandbox')` 不起作用，因为 Chromium 的 SUID 检查在 JavaScript 初始化**之前**执行。

**附加**: Ubuntu CI 无显示器，需 `xvfb-run` 提供虚拟 X server：
```yaml
- run: xvfb-run --auto-servernum npx playwright test --project=electron
```

### 坑 3: CI concurrency 误杀长测试

**症状**: E2E 测试运行到一半被取消，日志显示 `The operation was canceled`，quick job 通过但 electron-e2e 显示 cancelled。

**根因**: `concurrency.cancel-in-progress: true` + 同一 concurrency group，导致新 push 取消正在运行的 E2E 测试。

**修复**:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}-${{ github.job }}  # 加 job 名
  cancel-in-progress: false  # 不取消正在运行的
```

同时 `timeout-minutes` 设为 30（E2E + LLM 调用较慢）。

## 通用原则：测试 mock 与生产代码同步

当子进程管理类生产代码（如 bridge、worker）的启动流程变更后，测试 mock 必须同步：

1. **grep 生产代码中所有对 mock 对象的方法调用**（如 `this.process.once(...)`、`stdin.writable`），确保 mock 补齐所有被调用的方法和属性
2. **测试 helper 按生产流程顺序 feed 信号**（spawn → 就绪信号 → 初始化响应），不能跳步
3. **timing 要匹配**：生产代码中的 `setTimeout` 等待，测试中对应 `await new Promise(r => setTimeout(r, ...))`

## CI 配置参考

```yaml
name: Desktop CI

on:
  push:
    paths: ['apps/desktop/**', '.github/workflows/desktop-ci.yml']

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}-${{ github.job }}
  cancel-in-progress: false

jobs:
  electron-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: apps/desktop/package-lock.json }
      - run: npm ci
        working-directory: apps/desktop
      - run: npx playwright install chromium --with-deps
        working-directory: apps/desktop
      - run: npm run build
        working-directory: apps/desktop
      - name: Run Electron E2E
        run: xvfb-run --auto-servernum npx playwright test --project=electron
        working-directory: apps/desktop
        timeout-minutes: 30
```

## playwright.config.ts 参考

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  projects: [
    {
      name: 'electron',
      testMatch: ['full-electron.spec.ts'],
      timeout: 300000,  // 5 min — Electron boot 较慢
      // 不需要 headless 配置 —— connectOverCDP 自己处理
    },
  ],
  webServer: {
    command: 'python -m http.server 3458 --directory out/renderer',
    url: 'http://localhost:3458',
    reuseExistingServer: true,  // 避免 port 冲突
  },
})
```

## 排查清单

当 Electron E2E 测试失败时，按以下顺序排查：

1. **Electron 是否以 Node.js 模式运行？** → 检查 `ELECTRON_RUN_AS_NODE` 是否已 delete
2. **CDP 端点是否可用？** → 本地访问 `http://localhost:8315/json/version`
3. **CI 是否 SIGTRAP？** → 检查 `--no-sandbox` 是否作为 CLI 参数传递（非 appendSwitch）
4. **测试是否被取消？** → 检查 concurrency group 是否含 job 名、cancel-in-progress 是否 false
5. **mock 是否同步？** → 对比生产代码启动流程与测试 mock 的方法签名和信号 feed 顺序
