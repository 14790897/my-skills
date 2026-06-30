#!/usr/bin/env python3
"""docx-work-report 核心生成库。

提供 5 个文档生成函数：
  create_daily_report()    — 日报
  create_new_record()      — 新增记录
  create_weekly_report()   — 周报
  create_kanban()          — 任务看板（五表联动）
  create_ledger()          — 台账（四表联动）

通过独立的数据脚本调用（如 generate_w26.py），不是直接运行本文件。
所有输出文件保存到 OUTPUT_DIR，命名格式见 SKILL.md。
"""

import os

# 确保可导入 docx
try:
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx lxml")
    sys.exit(1)


OUTPUT_DIR = os.getcwd()


# ─────────────────────────────────────────────
# 日期格式化工具
# ─────────────────────────────────────────────

def format_date(d):
    """将日期格式化为 YYYY/M/D（不补零），如 2026/5/21、2026/6/3。
    支持 str（YYYY-MM-DD）或 date 对象。
    """
    if isinstance(d, str):
        # YYYY-MM-DD → YYYY/M/D
        parts = d.split("-")
        return f"{parts[0]}/{int(parts[1])}/{int(parts[2])}"
    from datetime import date as _date
    if isinstance(d, _date):
        return f"{d.year}/{d.month}/{d.day}"
    return str(d)


# ─────────────────────────────────────────────
# 通用工具函数
# ─────────────────────────────────────────────

def set_cell_shading(cell, color_hex):
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color_hex)
    shading.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading)


def set_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    borders = OxmlElement('w:tblBorders')
    for name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        b = OxmlElement(f'w:{name}')
        b.set(qn('w:val'), 'single')
        b.set(qn('w:sz'), '4')
        b.set(qn('w:space'), '0')
        b.set(qn('w:color'), '999999')
        borders.append(b)
    tblPr.append(borders)


def add_table(doc, headers, rows):
    """添加带样式的表格（自动计算列数）"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_table_borders(table)
    # 表头
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9)
                r.font.name = '宋体'
                r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        set_cell_shading(cell, 'D9E2F3')
    # 数据行
    for ri, row_data in enumerate(rows):
        for ci, text in enumerate(row_data):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = str(text)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = '宋体'
                    r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    doc.add_paragraph()
    return table


def add_heading(doc, text, level=2):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.name = '宋体'
        r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    return h


def add_para(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.name = '宋体'
    r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    if bold:
        r.bold = True


def new_doc():
    doc = Document()
    s = doc.sections[0]
    s.page_width = Cm(21)
    s.page_height = Cm(29.7)
    s.top_margin = Cm(2.0)
    s.bottom_margin = Cm(2.0)
    s.left_margin = Cm(2.0)
    s.right_margin = Cm(2.0)
    return doc


def title_page(doc, title_text):
    t = doc.add_heading(title_text, level=0)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in t.runs:
        r.font.name = '宋体'
        r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')


def save(doc, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    doc.save(path)
    print(f"  -> {filename}")
    return path


# ─────────────────────────────────────────────
# 日报生成
# ─────────────────────────────────────────────

def create_daily_report(date_str, name, project, reviewer, status,
                        goals_rows, tasks_rows, experiments_rows,
                        risks_rows, tomorrow_rows, self_eval_rows):
    """
    goals_rows:     [[类别, 内容, 验收标准, 完成情况], ...]
    tasks_rows:     [[序号, 任务, 输入方法, 产出, 验证方式, 状态], ...]
    experiments_rows: [[实验ID, 假设, 配置变更, 结果, 结论], ...] 或 [['无']]
    risks_rows:     [[问题, 影响, 已尝试, 需要支持], ...] 或 [['无']]
    tomorrow_rows:  [[优先级, 事项, 预期产出, 依赖], ...]
    self_eval_rows: [[维度, 自评, 导师反馈], ...]
    """
    doc = new_doc()
    title_page(doc, 'AI Agent 小团队实习生每日工作记录')

    add_heading(doc, '一、基本信息', 2)
    add_table(doc, ['项目', '内容'], [
        ['日期', date_str], ['姓名', name],
        ['所在小组/项目', project], ['导师/Reviewer', reviewer],
        ['今日工作时长', '8小时'], ['整体状态', status],
    ])

    add_heading(doc, '二、今日目标与实际结果', 2)
    add_table(doc, ['类别', '内容', '验收标准/证据', '完成情况'], goals_rows)

    add_heading(doc, '三、任务执行记录', 2)
    add_table(doc, ['序号', '任务', '输入与方法', '今日产出', '验证方式/指标', '状态与下一步'], tasks_rows)

    add_heading(doc, '四、实验/调试记录', 2)
    if experiments_rows and experiments_rows[0][0] != '无':
        add_table(doc, ['实验ID', '假设/问题', '配置或变更', '结果', '结论与下一步'], experiments_rows)
    else:
        add_para(doc, '无')

    add_heading(doc, '五、风险、问题与支持需求', 2)
    if risks_rows and risks_rows[0][0] != '无':
        add_table(doc, ['问题/风险', '影响范围', '已尝试方案', '需要支持'], risks_rows)
    else:
        add_para(doc, '无')

    add_heading(doc, '六、明日计划', 2)
    add_table(doc, ['优先级', '计划事项', '预期产出', '依赖/风险'], tomorrow_rows)

    add_heading(doc, '七、自评与导师反馈', 2)
    add_table(doc, ['维度', '自评', '导师反馈'], self_eval_rows)

    return save(doc, f'{name}-{date_str}-日报.docx')


# ─────────────────────────────────────────────
# 新增记录生成
# ─────────────────────────────────────────────

def create_new_record(date_str, name, project, module,
                      items_rows, knowledge_rows=None,
                      problems_rows=None, assets_rows=None,
                      weekly_rows=None):
    """
    items_rows:      [[编号, 类型, 标题, 来源, 价值, 处理建议], ...]
    knowledge_rows:   [[知识点, 场景, 关键步骤, 证据, 复用位置], ...]
    problems_rows:    [[描述, 复现条件, 严重程度, 临时处理, 负责人], ...]
    assets_rows:      [[类型, 名称, 用途, 维护人, 下一步], ...]
    weekly_rows:     [[事项, 同步位置, 原因, 证据], ...]
    """
    doc = new_doc()
    title_page(doc, 'AI Agent 实习生每日新增记录')

    add_heading(doc, '一、基本信息', 2)
    add_table(doc, ['项目', '内容'], [
        ['日期', date_str], ['记录人', name],
        ['关联项目', project], ['关联模块', module],
    ])

    add_heading(doc, '二、新增事项清单', 2)
    add_table(doc, ['编号', '新增类型', '标题', '来源', '价值/影响', '处理建议'], items_rows)

    add_heading(doc, '三、新知识/新方法沉淀', 2)
    if knowledge_rows:
        add_table(doc, ['知识点', '适用场景', '关键步骤/规则', '验证证据', '复用位置'], knowledge_rows)
    else:
        add_para(doc, '无')

    add_heading(doc, '四、新问题/缺陷记录', 2)
    if problems_rows:
        add_table(doc, ['问题描述', '复现条件', '严重程度', '临时处理', '负责人/截止时间'], problems_rows)
    else:
        add_para(doc, '无')

    add_heading(doc, '五、可复用资产登记', 2)
    if assets_rows:
        add_table(doc, ['资产类型', '名称/链接', '用途', '维护人', '下一步'], assets_rows)
    else:
        add_para(doc, '无')

    add_heading(doc, '六、是否同步到周报', 2)
    if weekly_rows:
        add_table(doc, ['事项', '同步位置', '原因', '证据材料'], weekly_rows)
    else:
        add_para(doc, '无')

    return save(doc, f'{name}-{date_str}-新增.docx')


# ─────────────────────────────────────────────
# 周报生成
# ─────────────────────────────────────────────

def create_weekly_report(week_id, week_range, name, reviewer, project, total_hours,
                         summary, conclusion_evidence,
                         outputs_rows, risks_rows,
                         tomorrow_rows, eval_rows):
    """
    summary:           一句话结论
    conclusion_evidence: 本周最重要证据
    outputs_rows:      [[类别, 产出, 证据, 状态], ...]
    risks_rows:        [[问题, 影响, 已采取动作, 需要支持], ...]
    tomorrow_rows:     [[优先级, 事项, 产物, 验收标准, 依赖], ...]
    eval_rows:         [[维度, 评分, 建议], ...]
    """
    doc = new_doc()
    title_page(doc, 'AI Agent 小团队实习生每周工作周报')

    add_heading(doc, '一、基本信息', 2)
    add_table(doc, ['项目', '内容'], [
        ['周次', week_id], ['周期', week_range],
        ['姓名', name], ['导师/Reviewer', reviewer],
        ['项目/小组', project], ['本周总工时', str(total_hours)],
    ])

    add_heading(doc, '二、本周一句话总结', 2)
    add_table(doc, ['一句话结论', '本周最重要证据'], [[summary, conclusion_evidence]])

    add_heading(doc, '三、本周关键产出', 2)
    add_table(doc, ['产出类别', '具体产出', '质量/影响证据', '当前状态'], outputs_rows)

    add_heading(doc, '四、问题、风险与决策需求', 2)
    add_table(doc, ['问题/风险', '影响', '已采取动作', '需要团队决策/支持'], risks_rows)

    add_heading(doc, '五、下周计划', 2)
    add_table(doc, ['优先级', '计划事项', '预期产物', '验收标准', '依赖'], tomorrow_rows)

    add_heading(doc, '六、导师评价', 2)
    add_table(doc, ['评价维度', '评分', '建议'], eval_rows)

    return save(doc, f'{name}-{week_id}-周报.docx')


# ─────────────────────────────────────────────
# 任务看板（五表联动）
# ─────────────────────────────────────────────

def create_kanban(week_id, week_range, name, reviewer,
                  tasks_rows, standup_rows, feedback_rows,
                  eval_rows, retro_rows):
    """
    tasks_rows:    [[T-001, 名称, 负责人, P0, Done, 验收标准, 截止日期], ...]
    standup_rows:  [[日期, 昨日完成, 今日计划, 阻塞, 需同步], ...]
    feedback_rows: [[日期, 对象, 类型, 反馈, 行动项, 复查时间], ...]  或 None
    eval_rows:     [[维度, 证据, 评分, 建议], ...]
    retro_rows:    [[复盘问题, 记录], ...]
    """
    doc = new_doc()
    title_page(doc, 'AI Agent 小团队任务看板与导师反馈')

    add_para(doc, f'周次：{week_id}（{week_range}）  |  姓名：{name}  |  导师：{reviewer}', bold=True)
    doc.add_paragraph()

    add_heading(doc, '表一：任务看板', 2)
    add_table(doc, ['任务ID', '任务名称', '负责人', '优先级', '状态', '验收标准', '截止日期'], tasks_rows)

    add_heading(doc, '表二：每日站会记录', 2)
    add_table(doc, ['日期', '昨日完成', '今日计划', '阻塞', '需同步事项'], standup_rows)

    add_heading(doc, '表三：导师反馈记录', 2)
    if feedback_rows:
        add_table(doc, ['日期', '反馈对象', '反馈类型', '具体反馈', '行动项', '复查时间'], feedback_rows)
    else:
        add_para(doc, '暂无数据')

    add_heading(doc, '表四：阶段评价表', 2)
    add_table(doc, ['评价维度', '观察证据', '评分', '改进建议'], eval_rows)

    add_heading(doc, '表五：团队复盘', 2)
    add_table(doc, ['复盘问题', '记录'], retro_rows)

    return save(doc, f'{name}-{week_id}-任务看板.docx')


# ─────────────────────────────────────────────
# 台账（四表联动）
# ─────────────────────────────────────────────

def create_ledger(week_id, week_range, name, project,
                  daily_rows, new_items_rows,
                  weekly_summary, kanban_rows):
    """
    daily_rows:      [[日期, 姓名, 模块, 类型, 目标, 产出, 证据, 验证, 状态, 工时, 阻塞, 明日计划, 导师备注], ...]
    new_items_rows:  [[日期, 类型, 模块, 标题, 来源, 价值, 建议, 进看板, 进周报, 证据, 备注], ...]
    weekly_summary:  [[week_id, range, name, project, 总结, 产出, 指标, 问题, 下周, 导师评价], ...]
    kanban_rows:     [[T-001, 名称, 负责人, P0, 状态, 模块, 验收标准, 开始日期, 截止日期, 阻塞, 备注], ...]
    """
    doc = new_doc()
    title_page(doc, 'AI Agent 小团队工作记录台账')

    add_para(doc, f'周次：{week_id}（{week_range}）  |  姓名：{name}  |  项目：{project}', bold=True)
    doc.add_paragraph()

    add_heading(doc, '表一：每日工作记录', 2)
    add_table(doc, ['日期', '姓名', 'Agent模块', '任务类型', '今日目标', '实际产出', '证据链接',
                    '验证方式/指标', '状态', '工时', '阻塞事项', '明日计划', '导师备注'], daily_rows)

    add_heading(doc, '表二：每日新增记录', 2)
    add_table(doc, ['日期', '新增类型', '关联模块', '标题', '来源', '价值/影响', '处理建议',
                    '是否进看板', '是否进周报', '证据/链接', '备注'], new_items_rows)

    add_heading(doc, '表三：周报汇总', 2)
    add_table(doc, ['周次', '周期', '姓名', '项目/小组', '一句话总结', '关键产出',
                    '指标/证据', '问题与风险', '下周计划', '导师评价'], weekly_summary)

    add_heading(doc, '表四：工具看板', 2)
    add_table(doc, ['任务ID', '任务名称', '负责人', '优先级', '状态', 'Agent模块', '验收标准',
                    '开始日期', '截止日期', '阻塞/依赖', '备注'], kanban_rows)

    return save(doc, f'{name}-{week_id}-台账.docx')
