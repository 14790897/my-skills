---
name: github-feishu-issue-sync
description: 将 GitHub 仓库的所有 Issue 同步到飞书多维表格。自动创建匹配字段（标题/编号/状态/链接/创建人/标签/创建时间/更新时间/正文），支持增量去重、dry-run 预览、批量写入。适用场景：用户提到同步 GitHub Issue 到飞书、把 Issue 写入多维表格、关联 GitHub 和飞书等需求。
agent_created: true
---

# GitHub Issue → 飞书多维表格同步

将任意 GitHub 仓库的所有 Issue 一次性/增量同步到飞书多维表格。

## 脚本

核心脚本: `scripts/sync_github_issues.py`

## 前置条件

### 1. 飞书应用

- 在 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用
- 开通权限: `bitable:app`（多维表格完整读写）
- 发布版本并审批通过
- 获取 App ID 和 App Secret

### 2. 文档级授权（91403 错误的根因）

飞书权限是两层架构：
- 第一层: 开放平台 API 权限（上一步）
- 第二层: 在具体文档/表格中添加应用为协作者

操作: 打开目标多维表格 → 右上角 `...` → `...更多` → `添加文档应用` → 搜索应用名 → 赋予「可编辑」权限

### 3. 环境变量

```bash
export FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxx"
# 可选，提高 GitHub API 速率限制
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxx"
```

## 用法

### 参数

| 参数 | 说明 |
|------|------|
| `--dry-run` | 预览模式，只显示不写入 |
| `--limit N` | 只处理前 N 条 Issue |
| `--force` | 跳过重复检查，强制全量写入 |
| `--include-pr` | 包含 Pull Request |
| `--fields JSON` | 手动指定表字段（类型: 1=文本, 2=数字, 5=日期, 15=超链接） |

### 示例

```bash
# 预览（推荐首次使用）
python scripts/sync_github_issues.py --dry-run --limit 3

# 正式同步
python scripts/sync_github_issues.py

# 强制覆盖（不去重）
python scripts/sync_github_issues.py --force
```

### 配置修改

脚本中需要修改的配置常量（在文件顶部）:

```python
GITHUB_REPO = "owner/repo"          # GitHub 仓库
FEISHU_DOC_TOKEN = "xyz123..."      # 飞书文档 token（从 URL 提取）
FEISHU_TABLE_ID = "tblxxxxxxxx"     # 飞书表 ID（从 URL 提取）
```

## 表结构约定

默认创建/映射以下字段:

| 飞书列 | 类型 | GitHub 来源 |
|--------|------|-------------|
| Issue编号 | 文本 (1) | issue.number |
| 标题 | 文本 (1) | issue.title |
| 状态 | 文本 (1) | issue.state |
| 链接 | 超链接 (15) | issue.html_url |
| 创建人 | 文本 (1) | issue.user.login |
| 标签 | 文本 (1) | issue.labels[].name |
| 创建时间 | 日期 (5) | issue.created_at |
| 更新时间 | 日期 (5) | issue.updated_at |
| 正文 | 文本 (1) | issue.body |

## 工作流程

1. 拉取 GitHub 所有 Issue（分页，默认过滤 PR）
2. 连接飞书获取表字段结构
3. 自动映射字段名（支持中英文模糊匹配）
4. 读取已有记录按 Issue 编号去重
5. 批量写入新记录（500 条/批）
6. 输出同步结果

## 踩坑记录

- **91403 Forbidden**: 缺少第二层文档授权，需要在表格页面「添加文档应用」
- **DatetimeFieldConvFail**: 日期字段必须用毫秒时间戳，不能用 ISO 字符串
- **中文字段名乱码**: curl 在 Windows bash 下传中文会编码错误，用 Python requests 代替
- **主列不可删除**: 飞书多维表格的主列是硬性设计，只能改名或隐藏
