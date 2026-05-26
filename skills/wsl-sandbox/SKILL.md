---
name: wsl-sandbox
slug: wsl-sandbox
version: 1.2.0
agent_created: true
description: "WSL2 AI 沙箱操作指南。在 Windows 上通过 WSL2 执行 Linux 命令。沙箱以 root 运行，无需密码。适用于：需要运行 Linux 命令、脚本或工具。触发词：wsl sandbox、wsl沙箱、linux命令、隔离执行、AI沙箱、sandbox_exec、sandbox_setup。"
metadata:
  emoji: "🐧"
  os: ["win32"]
  requires:
    bins: ["wsl.exe"]
---

# WSL2 AI 沙箱使用指南

## 核心原则

**使用导入的沙箱实例，root 身份运行，无需密码。**

## 首次准备：生成沙箱镜像

```powershell
# 导出已有的 WSL 发行版（如 Ubuntu）为镜像
wsl.exe --export Ubuntu C:\TempSandbox\full_image\ubuntu-full.tar.gz
```

## 第一步：注册沙箱（sandbox_setup）

```powershell
wsl.exe --import AIShadowSandbox C:\TempSandbox\ActiveInstance C:\TempSandbox\full_image\ubuntu-full.tar.gz --version 2
```

已注册则跳过。用 `wsl.exe --list --quiet` 确认 `AIShadowSandbox` 存在。

## 执行 Linux 命令（sandbox_exec）

**直接用 Bash 工具（最常用方式）：**

```bash
wsl.exe -d AIShadowSandbox -- bash -c "uname -a && whoami"
```

**多行脚本：**

```bash
wsl.exe -d AIShadowSandbox -- bash << 'EOF'
apt-get update -y
apt-get install -y python3
EOF
```

**销毁沙箱（sandbox_destroy）：**

```powershell
wsl.exe --unregister AIShadowSandbox
```

## AI 使用流程

```
1. wsl.exe --list --quiet 确认 AIShadowSandbox 存在
2. 不存在 → wsl.exe --import 注册沙箱
3. 执行命令：wsl.exe -d AIShadowSandbox -- bash -c "命令"
4. （可选）任务完成后 wsl.exe --unregister 销毁
```


## 注意事项

- **root 身份**：沙箱默认以 root 运行，无需 `sudo` 和密码
- **每次 `bash -c` 是独立会话**：环境变量、cd 不跨命令保持；需要保持状态时用多行脚本一次执行
- **文件系统跨命令保持**：安装的软件包、写入的文件在沙箱生命周期内持久
- **Windows 路径映射**：`C:\foo\bar` → `/mnt/c/foo/bar`
- **输出编码**：WSL 输出 UTF-8，Bash 工具直接读即可

## 状态持久性

- 文件系统（已安装软件包、写入文件）在沙箱生命周期内持久
- shell 变量、cd 目录、后台进程不跨命令保持
  
## 首次安装 WSL（系统没有任何发行版时）

```powershell
# 查看可安装的发行版
wsl.exe --list --online

# 安装 Ubuntu（推荐）
wsl.exe --install -d Ubuntu
```

安装完成后重新执行第一步。
