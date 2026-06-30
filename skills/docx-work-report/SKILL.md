# docx-work-report-general

将口语化的工作内容描述转化为结构化的 Word 文档，适用于实习生/小团队的日常工作记录。

**注意**：此为通用版，不含具体姓名等个人信息。首次使用需配置姓名和导师。

## 触发条件

- "日报"、"新增"、"周报"、"任务看板"、"台账"、"生成docx"、"写日报"、"填新增"
- 用户提供某天/某周的工作内容并要求生成文档

## 依赖

- Python 3.12+，需安装 `python-docx` 和 `lxml`
- 安装命令：`pip install python-docx lxml`
- 运行时使用当前环境的 Python

## 工作流程

### 第一步：收集信息

**需要用户提供：**
- 姓名、导师姓名（首次使用，后续沿用）
- 工作/任务内容（口语化即可）

**可选项（有则填，无则跳过）：**
- 实验记录、调试过程、风险问题
- 导师反馈、每日站会信息
- 下周计划、明日计划

### 第二步：确定输出类型

| 用户请求 | 输出文件 | 命名格式 |
|---------|---------|---------|
| 日报 | 日报.docx | 姓名-YYYY-MM-DD-日报.docx |
| 新增记录 | 新增.docx | 姓名-YYYY-MM-DD-新增.docx |
| 周报 | 周报.docx | 姓名-YYYY-WXX-周报.docx |
| 任务看板 | 任务看板.docx | 姓名-YYYY-WXX-任务看板.docx |
| 台账 | 台账.docx（含4表） | 姓名-YYYY-WXX-台账.docx |

### 第三步：运行生成脚本

**核心库**：`scripts/generate_all.py` 提供 5 个函数（`create_daily_report`、`create_new_record`、`create_weekly_report`、`create_kanban`、`create_ledger`）。

**实际生成模式**：以已有的数据脚本为模板，复制后只替换数据区段（`d0622`、`new_0622`、`weekly_data`、`kanban_data`、`ledger_data` 等变量内容）。一次运行生成该周全部文档。

脚本通用结构（复制后只改 NAME、REVIEWER 和数据）：
```python
import os, sys
sys.path.insert(0, r"<skill-path>/scripts")
from generate_all import (create_daily_report, create_new_record,
    create_weekly_report, create_kanban, create_ledger)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
import generate_all; generate_all.OUTPUT_DIR = OUTPUT_DIR

NAME = "填写姓名"
REVIEWER = "填写导师"
PROJECT = "填写项目名"

# 数据定义区（唯一需要修改的部分）
d0622 = { "date": "2026-06-22", "goals": [...], ... }
# ... 更多数据 ...

# 生成区（不变）
create_daily_report(date_str=d0622["date"], ...)    # 日报
create_new_record(date_str=new_0622["date"], ...)    # 新增
create_weekly_report(...)                            # 周报
create_kanban(...)                                   # 任务看板
create_ledger(...)                                   # 台账
```

**重要规则**：
- 脚本结构不变，只替换 NAME/REVIEWER 和数据；不要每次重写生成逻辑
- 通过 `generate_all.OUTPUT_DIR` 覆盖输出目录到脚本所在位置
- 日期在表格内使用 `YYYY/M/D`（不补零），由 `format_date()` 辅助

## 文档结构规范

### 日报结构（7节）

1. 基本信息（日期、姓名、项目、导师、工时、状态）
2. 今日目标与实际结果（计划/实际/差异）
3. 任务执行记录（序号、任务、输入方法、产出、验证方式、状态）
4. 实验/调试记录（实验ID、假设、配置变更、结果、结论）— 无则写"无"
5. 风险、问题与支持需求 — 无则写"无"
6. 明日计划（优先级、事项、预期产出、依赖）
7. 自评与导师反馈（维度、自评、导师反馈留空）

### 新增记录结构（6节）

1. 基本信息（日期、记录人、项目、模块）
2. 新增事项清单（编号、类型、标题、来源、价值、处理建议）
3. 新知识/新方法沉淀 — 无则写"无"
4. 新问题/缺陷记录 — 无则写"无"
5. 可复用资产登记 — 无则写"无"
6. 是否同步到周报 — 无则写"无"

### 周报结构（6节）

1. 基本信息（周次、周期、姓名、导师、项目、总工时）
2. 一句话总结（结论 + 证据）
3. 本周关键产出（类别、产出、证据、状态）
4. 问题、风险与决策需求
5. 下周计划（优先级、事项、产物、验收标准、依赖）
6. 导师评价（留空待填）

### 任务看板（五表联动）

1. 表一：任务看板（T-001递增，P0/P1/P2优先级，Backlog/Todo/Doing/Review/Done/Blocked状态）
2. 表二：每日站会记录
3. 表三：导师反馈记录 — 无数据则写"暂无数据"
4. 表四：阶段评价表（维度、证据、评分留空、建议留空）
5. 表五：团队复盘（5个固定问题）

### 台账（四表联动）

1. 表一：每日工作记录（整周逐天）
2. 表二：每日新增记录（整周逐天）
3. 表三：周报汇总（一行）
4. 表四：工具看板（从表一表二提炼进行中/待办事项）

## 排版规范

- 页面：A4 (21cm × 29.7cm)，上下左右边距 2.0cm
- 标题：宋体
- 正文字号：10pt，表格字号 9pt
- 表格：居中对齐，表头浅蓝底色 (#D9E2F3)，灰色边框 (#999999)
- 表格内字体：宋体，表头加粗居中
- 日期格式：文件名用 YYYY-MM-DD；表格内日期用 YYYY/M/D（不补零），例如 2026/5/21、2026/6/3
- 周次格式：YYYY-WXX

## 枚举值参考

### 优先级
P0（阻塞/核心）、P1（重要）、P2（锦上添花）

### 状态
Backlog / Todo / Doing / Review / Done / Blocked

### 新增类型
知识 / 问题 / 资产 / 方案

### 任务类型
开发 / 实验 / 调研 / 文档 / 会议 / 调试 / Other

### Agent模块
Planner / RAG / Tool Use / Memory / Eval / UI / Infra / Other

## 关键规则

1. 不编造用户未提供的信息，缺失项填"-"
2. 导师评价/反馈列始终留空，等待导师填写
3. 任务看板中 Done 的任务带截止日期，未完成的不填
4. 四表/五表联动：各表信息自动流转，保持一致性
5. 产出文件的命名严格按格式，便于排序和查找
