---
name: wsl-sandbox
slug: wsl-sandbox
version: 1.1.0
agent_created: true
description: "WSL2 AI 沙箱操作指南。在 Windows 上通过 WSL2 执行 Linux 命令。适用于：需要运行 Linux 命令、脚本或工具；优先使用系统现有 WSL 发行版，无需准备镜像文件。触发词：wsl sandbox、wsl沙箱、linux命令、隔离执行、AI沙箱、sandbox_exec。"
metadata:
  emoji: "🐧"
  os: ["win32"]
  requires:
    bins: ["wsl.exe"]
---

# WSL2 AI 沙箱使用指南

## 核心原则

**优先使用系统已有的 WSL 发行版，无需准备镜像文件，开箱即用。**

## 第一步：查看可用的 WSL 发行版

```bash
wsl.exe --list --quiet
```

选择输出中已有的发行版名称（如 `Ubuntu`、`Ubuntu-22.04`、`Debian` 等），后续命令中用 `-d <名称>` 指定。

如果没有任何发行版，参考末尾「首次安装 WSL」一节。

## 执行 Linux 命令

**直接用 Bash 工具（最常用方式）：**

```bash
wsl.exe -d Ubuntu -- bash -c "uname -a && whoami"
```


## AI 使用流程

```
1. 查可用发行版：wsl.exe --list --quiet
2. 挑一个（优先 Ubuntu 或 Debian）
3. 执行命令：wsl.exe -d <发行版名> -- bash -c "命令"
4. 处理输出
```


## 注意事项

- **每次 `bash -c` 是独立会话**：环境变量、cd 不跨命令保持；需要保持状态时用多行脚本一次执行
- **Windows 路径映射**：`C:\foo\bar` → `/mnt/c/foo/bar`
- **输出编码**：WSL 输出 UTF-8，Bash 工具直接读即可
- **权限**：默认以 WSL 配置的用户运行（通常是普通用户），需要 root 加 `sudo` 或 `wsl.exe -d Ubuntu -u root -- bash -c "命令"`

## 隔离沙箱模式（可选，需要镜像文件时才用）

如果需要完全隔离、用完即销毁的环境，可以导入自定义镜像：

```powershell
# 从现有发行版导出镜像
wsl.exe --export Ubuntu C:\TempSandbox\ubuntu-base.tar.gz

# 导入为独立沙箱实例
wsl.exe --import MySandbox C:\TempSandbox\MySandbox C:\TempSandbox\ubuntu-base.tar.gz --version 2

# 使用沙箱
wsl.exe -d MySandbox -- bash -c "命令"

# 用完销毁
wsl.exe --unregister MySandbox
```

## 首次安装 WSL（系统没有任何发行版时）

```powershell
# 查看可安装的发行版
wsl.exe --list --online

# 安装 Ubuntu（推荐）
wsl.exe --install -d Ubuntu
```

安装完成后重新执行第一步。
