#!/usr/bin/env python3
"""
GitHub Issues → 飞书多维表格 同步脚本

用法:
  python sync_github_issues.py [--dry-run] [--no-pr] [--force]

环境变量:
  FEISHU_APP_ID      飞书应用 App ID
  FEISHU_APP_SECRET  飞书应用 App Secret
  GITHUB_TOKEN       GitHub Personal Access Token (可选，提高速率限制)

飞书应用所需权限 (在飞书开放平台开启):
  - bitable:app (多维表格读写)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

import requests

# ─── 配置 ───────────────────────────────────────────────
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "1")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "2")
GITHUB_REPO = "14790897/miqi"
FEISHU_DOC_TOKEN = "3"
FEISHU_TABLE_ID = "4"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# 飞书 API 基础地址
FEISHU_BASE = "https://open.feishu.cn/open-apis"


# ─── 飞书 API 封装 ──────────────────────────────────────

class FeishuAPI:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self.token_expires = 0

    def _get_token(self):
        """获取 / 刷新 tenant_access_token"""
        if self.token and time.time() < self.token_expires - 60:
            return self.token

        print("[飞书] 获取 tenant_access_token ...")
        resp = requests.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书认证失败: {data.get('msg')} (code={data.get('code')})")

        self.token = data["tenant_access_token"]
        self.token_expires = time.time() + data.get("expire", 7200)
        print(f"[飞书] Token 获取成功，有效期 {data.get('expire')} 秒")
        return self.token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def get_table_fields(self, doc_token, table_id):
        """获取多维表格的字段列表"""
        url = f"{FEISHU_BASE}/bitable/v1/apps/{doc_token}/tables/{table_id}/fields"
        resp = requests.get(url, headers=self._headers())
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取表字段失败: {data.get('msg')} (code={data.get('code')})\n"
                               f"请确保飞书应用已开启 bitable:app 权限")
        return data["data"]["items"]

    def list_records(self, doc_token, table_id, page_size=500):
        """列出表中所有记录（用于去重检查）"""
        records = []
        page_token = None

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            url = f"{FEISHU_BASE}/bitable/v1/apps/{doc_token}/tables/{table_id}/records"
            resp = requests.get(url, headers=self._headers(), params=params)
            data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f"读取记录失败: {data.get('msg')}")

            items = data.get("data", {}).get("items", [])
            records.extend(items)

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data["data"].get("page_token")

        return records

    def batch_create_records(self, doc_token, table_id, records):
        """批量创建记录（最多 500 条/次）"""
        url = f"{FEISHU_BASE}/bitable/v1/apps/{doc_token}/tables/{table_id}/records/batch_create"
        payload = {"records": records}
        resp = requests.post(url, headers=self._headers(), json=payload)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"批量创建记录失败: {data.get('msg')}")
        return data["data"]["records"]


# ─── GitHub API 封装 ────────────────────────────────────

class GitHubAPI:
    BASE = "https://api.github.com"

    def __init__(self, token=""):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch_all_issues(self, repo, include_pull_requests=True):
        """拉取所有 Issue（分页）"""
        issues = []
        page = 1

        while True:
            url = f"{self.BASE}/repos/{repo}/issues"
            params = {"state": "all", "per_page": 100, "page": page}
            print(f"[GitHub] 拉取第 {page} 页 ...")
            resp = requests.get(url, headers=self.headers, params=params)

            if resp.status_code != 200:
                raise RuntimeError(f"GitHub API 错误: {resp.status_code} {resp.text[:200]}")

            data = resp.json()
            if not data:
                break

            issues.extend(data)
            page += 1

            # 检查是否还有下一页
            if "link" not in resp.headers or 'rel="next"' not in resp.headers.get("link", ""):
                break

        # 默认过滤掉 PR（除非指定保留）
        if not include_pull_requests:
            issues = [i for i in issues if "pull_request" not in i]

        print(f"[GitHub] 共拉取 {len(issues)} 条记录")
        return issues


# ─── 字段映射 ───────────────────────────────────────────

def build_field_map(feishu_fields, github_issue_sample):
    """根据飞书表结构自动推断字段映射"""
    # 飞书字段名 → GitHub 数据路径
    candidates = {
        # 优先匹配 — 当前表格式
        "Issue编号": "number",
        "标题": "title",
        "编号": "number",
        "状态": "state",
        "链接": "html_url",
        "创建人": "user.login",
        "标签": "labels",
        "创建时间": "created_at",
        "更新时间": "updated_at",
        "正文": "body",
        # 其他常见列名
        "URL": "html_url",
        "作者": "user.login",
        "负责人": "assignee.login",
        "里程碑": "milestone.title",
        "评论数": "comments",
        "关闭时间": "closed_at",
        "描述": "body",
        "内容": "body",
        "类型": "type",
        "Issue URL": "html_url",
        "Issue Title": "title",
        "Issue State": "state",
    }

    field_map = {}
    for field in feishu_fields:
        field_name = field.get("field_name", "")
        field_type = field.get("type", 0)

        # 尝试精确匹配
        if field_name in candidates:
            field_map[field_name] = {
                "gh_key": candidates[field_name],
                "feishu_field": field_name,
                "type": field_type,
            }
            continue

        # 模糊匹配
        lower = field_name.lower().replace(" ", "").replace("_", "")
        for cn_key, gh_key in candidates.items():
            if cn_key.lower().replace(" ", "").replace("_", "").lower() == lower:
                field_map[field_name] = {
                    "gh_key": gh_key,
                    "feishu_field": field_name,
                    "type": field_type,
                }
                break

    print(f"[映射] 自动匹配了 {len(field_map)}/{len(feishu_fields)} 个字段:")
    for k, v in field_map.items():
        print(f"  {k} ← GitHub.{v['gh_key']} (type={v['type']})")

    unmatched = [f.get("field_name") for f in feishu_fields if f.get("field_name") not in field_map]
    if unmatched:
        print(f"[映射] 未匹配的飞书字段: {unmatched}")

    return field_map


def extract_value(issue, gh_key):
    """从 GitHub issue 对象中提取指定字段的值"""
    keys = gh_key.split(".")
    value = issue
    for k in keys:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return None
    return value


def format_field_value(value, field_type):
    """根据飞书字段类型格式化值"""
    if value is None:
        return None

    field_type = int(field_type)

    # 1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选框,
    # 11=人员, 15=超链接, 17=附件, 1001=公式, 1002=关联
    if field_type == 1:  # 文本
        # 标签列表 → 逗号分隔
        if isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                value = ", ".join(v.get("name", str(v)) for v in value)
            else:
                value = ", ".join(str(v) for v in value)
        # Issue 编号格式化（非列表的数字）
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(int(value))
        return str(value)

    elif field_type == 2:  # 数字
        if isinstance(value, (int, float)):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return str(value)

    elif field_type == 5:  # 日期 → 毫秒时间戳
        if isinstance(value, str):
            # GitHub 格式: "2026-06-30T01:24:33Z" → milliseconds
            try:
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                dt = datetime.fromisoformat(value)
                # Feishu 日期字段要求毫秒级时间戳
                return int(dt.timestamp() * 1000)
            except (ValueError, TypeError):
                return None
        return None

    elif field_type == 15:  # 超链接
        return {"link": str(value), "text": str(value)[:50]}

    else:
        # 默认转字符串
        return str(value)


def build_record(issue, field_map):
    """根据字段映射构建一条飞书记录"""
    fields = {}
    for feishu_field, mapping in field_map.items():
        value = extract_value(issue, mapping["gh_key"])
        formatted = format_field_value(value, mapping["type"])
        if formatted is not None:
            fields[feishu_field] = formatted
    return {"fields": fields}


# ─── 主流程 ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GitHub Issues → 飞书多维表格同步")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入")
    parser.add_argument("--include-pr", action="store_true", help="包含 Pull Request（默认过滤）")
    parser.add_argument("--force", action="store_true", help="强制写入，不去重")
    parser.add_argument("--limit", type=int, default=0, help="只同步前 N 条（0=全部）")
    parser.add_argument(
        "--fields",
        type=str,
        default="",
        help="手动指定飞书表字段和类型，JSON 格式。"
        '例: \'[{"field_name":"标题","type":1},{"field_name":"编号","type":2}]\''
        "（type: 1=文本, 2=数字, 5=日期, 15=超链接）",
    )
    args = parser.parse_args()

    # ── 1. 拉取 GitHub Issues ──
    print("=" * 60)
    print(">>> 步骤 1: 拉取 GitHub Issues")
    print("=" * 60)
    gh = GitHubAPI(token=GITHUB_TOKEN)
    issues = gh.fetch_all_issues(GITHUB_REPO, include_pull_requests=args.include_pr)

    if args.limit > 0:
        issues = issues[:args.limit]
        print(f"[GitHub] 限制为前 {args.limit} 条")

    if not issues:
        print("没有 Issue 需要同步")
        return

    # 统计
    real_issues = [i for i in issues if "pull_request" not in i]
    prs = [i for i in issues if "pull_request" in i]
    print(f"  其中 Issue: {len(real_issues)} 条, PR: {len(prs)} 条")

    # ── 2. 连接飞书，获取表结构 ──
    print("\n" + "=" * 60)
    print(">>> 步骤 2: 连接飞书，获取表结构")
    print("=" * 60)
    feishu = FeishuAPI(FEISHU_APP_ID, FEISHU_APP_SECRET)

    fields = None
    if args.fields:
        # 手动指定字段
        try:
            fields = json.loads(args.fields)
            if isinstance(fields, dict):
                fields = [fields]
            print(f"[飞书] 手动指定 {len(fields)} 个字段")
            for f in fields:
                print(f"  - {f.get('field_name')} (type={f.get('type')})")
        except json.JSONDecodeError as e:
            print(f"字段格式错误: {e}")
            return
    else:
        try:
            fields = feishu.get_table_fields(FEISHU_DOC_TOKEN, FEISHU_TABLE_ID)
            print(f"[飞书] 表中有 {len(fields)} 个字段")
            for f in fields:
                print(f"  - {f.get('field_name')} (type={f.get('type')}, id={f.get('field_id')})")
        except RuntimeError as e:
            print(f"\n⚠️  无法获取飞书表结构: {e}")
            print("\n方案 A — 开通权限后重试:")
            print("  1. 打开 https://open.feishu.cn/app/cli_aac89a9e94b0dcc7/auth")
            print("  2. 开通权限: bitable:app")
            print("  3. 发布新版本并审批通过")
            print("\n方案 B — 手动指定表字段（跳过权限）:")
            print('  python sync_github_issues.py --dry-run --fields \'[{"field_name":"标题","type":1},{"field_name":"编号","type":2},{"field_name":"状态","type":1},{"field_name":"链接","type":15}]\'')
            return

    # ── 3. 字段映射 ──
    print("\n" + "=" * 60)
    print(">>> 步骤 3: 字段映射")
    print("=" * 60)
    sample_issue = issues[0]
    field_map = build_field_map(fields, sample_issue)

    if not field_map:
        print("\n⚠️  没有成功匹配任何字段，请检查飞书表格的列名是否与以下关键词一致:")
        print("  标题, 编号, 状态, 链接, 创建人, 标签, 创建时间, 更新时间, 正文")
        return

    # ── 4. 去重检查 ──
    existing_numbers = set()
    if not args.force:
        print("\n" + "=" * 60)
        print(">>> 步骤 4: 去重检查（读取现有记录）")
        print("=" * 60)
        try:
            existing = feishu.list_records(FEISHU_DOC_TOKEN, FEISHU_TABLE_ID)
            print(f"[飞书] 表中已有 {len(existing)} 条记录")

            # 尝试从现有记录中提取编号
            number_field = None
            for fname, mapping in field_map.items():
                if mapping["gh_key"] == "number":
                    number_field = fname
                    break

            if number_field:
                for rec in existing:
                    val = rec.get("fields", {}).get(number_field)
                    if val is not None:
                        # 支持 "93" 和 "#93" 两种格式
                        try:
                            s = str(val).lstrip("#")
                            existing_numbers.add(int(s))
                        except (ValueError, TypeError):
                            pass
                print(f"[去重] 提取到 {len(existing_numbers)} 个已有编号")
            else:
                print("[去重] 表中没有编号字段，跳过去重")
        except Exception as e:
            print(f"[去重] 读取失败: {e}，将跳过去重")
    else:
        print("\n>>> 步骤 4: 跳过（--force）")

    # ── 5. 构建记录并写入 ──
    print("\n" + "=" * 60)
    print(">>> 步骤 5: 同步数据")
    print("=" * 60)

    new_records = []
    skipped = 0
    for issue in issues:
        number = issue.get("number")
        if number in existing_numbers:
            skipped += 1
            continue

        record = build_record(issue, field_map)
        new_records.append(record)

    print(f"  待写入: {len(new_records)} 条, 已跳过: {skipped} 条")

    if args.dry_run:
        print("\n" + "=" * 60)
        print(">>> DRY RUN 模式 — 预览前 5 条数据")
        print("=" * 60)
        for i, record in enumerate(new_records[:5]):
            print(f"\n--- 记录 #{i+1} ---")
            print(json.dumps(record, ensure_ascii=False, indent=2))
        print(f"\n共 {len(new_records)} 条记录待写入（--dry-run 模式未实际写入）")
        if len(new_records) > 5:
            print("（仅展示前 5 条）")
        return

    if not new_records:
        print("\n✅ 没有新记录需要写入")
        return

    # 分批写入（飞书 API 限制 500 条/次）
    batch_size = 500
    total_written = 0
    for i in range(0, len(new_records), batch_size):
        batch = new_records[i : i + batch_size]
        try:
            feishu.batch_create_records(FEISHU_DOC_TOKEN, FEISHU_TABLE_ID, batch)
            total_written += len(batch)
            print(f"  ✓ 写入 {i+1}-{min(i+batch_size, len(new_records))}/{len(new_records)}")
        except RuntimeError as e:
            print(f"  ✗ 批次 {i//batch_size+1} 写入失败: {e}")
            # 如果大批量失败，逐条重试
            print("  尝试逐条写入...")
            for record in batch:
                try:
                    feishu.batch_create_records(FEISHU_DOC_TOKEN, FEISHU_TABLE_ID, [record])
                    total_written += 1
                except Exception as e2:
                    print(f"    ✗ {record.get('fields',{}).get('标题','?')}: {e2}")

    print("\n" + "=" * 60)
    print(f"✅ 同步完成! 成功写入 {total_written} 条，跳过 {skipped} 条")
    print(f"   飞书表格: https://zaqq202feok.feishu.cn/wiki/{FEISHU_DOC_TOKEN}?table={FEISHU_TABLE_ID}")
    print("=" * 60)


if __name__ == "__main__":
    main()
