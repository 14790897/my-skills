---
name: wsl-sandbox
slug: wsl-sandbox
version: 1.0.0
agent_created: true
description: >
  WSL2 AI 影子沙箱操作指南。在 Windows 上通过 WSL2 隔离沙箱执行 Linux 命令，无需 MCP Server。
  适用于：需要运行 Linux 命令、脚本或工具；需要隔离执行环境；需要在沙箱中安装依赖并保留状态。
  触发词：wsl sandbox、wsl沙箱、linux命令、隔离执行、AI沙箱、sandbox_exec、sandbox_setup、sandbox_destroy。
metadata:
  emoji: "🐧"
  os: ["win32"]
  requires:
    bins: ["wsl.exe"]
---

# WSL2 AI 影子沙箱使用指南

## 沙箱架构

| 常量 | 值 |
|------|-----|
| 沙箱实例名称 | `AIShadowSandbox` |
| 根文件系统镜像 | `C:\TempSandbox\full_image\ubuntu-full.tar.gz` |
| 沙箱工作目录 | `C:\TempSandbox\ActiveInstance` |

## 三个核心操作

### 1. 检查沙箱状态

```powershell
wsl.exe --list --quiet
```

输出中包含 `AIShadowSandbox` → 沙箱已就绪，可直接执行命令。
否则需要先注册沙箱。

### 2. 注册沙箱（sandbox_setup）

```powershell
wsl.exe --import AIShadowSandbox C:\TempSandbox\ActiveInstance C:\TempSandbox\full_image\ubuntu-full.tar.gz --version 2
```

- 幂等操作：沙箱已存在时不会报错，直接使用即可
- 首次注册耗时较长（解压 tar.gz），后续启动瞬间完成
- 沙箱采用 --keep 模式：注册后持续存在，直到显式销毁

### 3. 执行 Linux 命令（sandbox_exec）

**单条命令：**
```powershell
echo "ls -la /home" | wsl.exe -d AIShadowSandbox -- bash
```

**多行脚本（推荐用 Python 调用，避免 PowerShell 编码问题）：**
```python
import subprocess

commands = """
apt-get update -y
apt-get install -y python3 python3-pip
python3 --version
""".strip()

process = subprocess.Popen(
    ["wsl.exe", "-d", "AIShadowSandbox", "--", "bash"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=0x08000000  # CREATE_NO_WINDOW
)
stdout, stderr = process.communicate(input=commands.encode("utf-8"), timeout=120)
print(stdout.decode("utf-8", errors="replace"))
print(stderr.decode("utf-8", errors="replace"))
```

**直接用 Bash 工具执行（最简方式）：**
```bash
echo "whoami && uname -a && ls /tmp" | wsl.exe -d AIShadowSandbox -- bash
```

### 4. 销毁沙箱（sandbox_destroy）

```powershell
wsl.exe --unregister AIShadowSandbox
```

⚠️ 销毁后沙箱内所有数据永久丢失，不可恢复。

## AI 使用流程（标准工作流）

```
1. 检查沙箱是否运行
   ↓ 未运行 → 执行 wsl --import 注册
   ↓ 已运行 → 直接跳到第2步

2. 用 Bash 工具执行命令：
   echo "你的命令" | wsl.exe -d AIShadowSandbox -- bash

3. 处理输出结果

4. （可选）任务完成后销毁沙箱：
   wsl.exe --unregister AIShadowSandbox
```

## 沙箱状态持久性

- **文件系统状态跨命令保持**：本次 exec 写入的文件，下次 exec 仍然存在
- **进程不跨命令保持**：每次 exec 都是新的 bash 会话，后台进程会被清理

## 编码注意事项

- **命令编码**：命令字符串用 UTF-8 编码传入
- **输出编码**：stdout/stderr 用 UTF-8 解码（`errors="replace"`）
- **Windows 路径**：在沙箱内访问 Windows 文件用 `/mnt/c/...`（对应 `C:\...`）
- **WSL --list 输出**：`wsl --list` 在 Windows 下输出 UTF-16-LE，检查时注意解码

## 故障排查

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| `wsl --import` 失败 | tar.gz 不存在或路径错误 | 确认 `C:\TempSandbox\full_image\ubuntu-full.tar.gz` 存在 |
| 命令超时 | 操作耗时过长 | 增大 timeout，或拆分为多步执行 |
| 沙箱内找不到命令 | 基础镜像未包含该工具 | 先用 `apt-get install` 安装 |
| 文件权限问题 | 需要 root | 镜像默认 root 用户，直接操作即可 |
| `/mnt/c` 无法访问 | WSL2 挂载未就绪 | 执行 `ls /mnt/c` 触发挂载 |
