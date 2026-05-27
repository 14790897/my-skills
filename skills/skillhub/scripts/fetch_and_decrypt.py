"""
SkillHub encrypted skill manager — install, decrypt, or one-shot fetch+decrypt.

Usage:
    python fetch_and_decrypt.py <skill-name> --install
    python fetch_and_decrypt.py <skill-name> --local
    python fetch_and_decrypt.py <skill-name>

Key is read from SKILL_ENCRYPTION_KEY env var (auto-injected).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_API = "https://skills.sixiangjia.de/api/skills"


def configure_console_encoding() -> None:
    if os.name != "nt":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def extract_metadata(raw: bytes) -> dict:
    """Extract metadata from .dat binary without decrypting the body."""
    if len(raw) < 5:
        raise ValueError("Invalid .dat: too short")
    meta_len = struct.unpack("<I", raw[:4])[0]
    meta_bytes = raw[4 : 4 + meta_len]
    return json.loads(meta_bytes.decode("utf-8"))


def decrypt_dat(raw: bytes, key: bytes) -> str:
    """Decrypt .dat binary → full SKILL.md text."""
    if len(raw) < 5:
        raise ValueError("Invalid .dat: too short")

    meta_len = struct.unpack("<I", raw[:4])[0]
    meta_bytes = raw[4 : 4 + meta_len]
    remainder = raw[4 + meta_len :]

    if len(remainder) < 13:
        raise ValueError("Invalid .dat: insufficient ciphertext")

    metadata = json.loads(meta_bytes.decode("utf-8"))

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    nonce = remainder[:12]
    ciphertext = remainder[12:]
    body = aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    lines = ["---"]
    for k, v in metadata.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


_DEFAULT_KEY = "0322a06e6803ebcc8b96b9dc3221e1a2e49d399774c046b70014103f13084312"


def resolve_key() -> bytes:
    key_hex = os.environ.get("SKILL_ENCRYPTION_KEY", _DEFAULT_KEY)
    if not key_hex or len(key_hex) != 64:
        print("ERROR: SKILL_ENCRYPTION_KEY 环境变量未配置", file=sys.stderr)
        sys.exit(1)
    return bytes.fromhex(key_hex)


def download_raw(skill_name: str, api_url: str) -> bytes:
    """Download encrypted skill from API, return binary .dat bytes."""
    url = f"{api_url.rstrip('/')}/{skill_name}/encrypted"
    print(f"Downloading from {url} ...", file=sys.stderr)
    try:
        resp = urllib.request.urlopen(url)
        api_data = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR: 下载失败 — {e}", file=sys.stderr)
        sys.exit(1)

    if not api_data.get("encrypted"):
        print("ERROR: 该技能不是加密技能，无需解密", file=sys.stderr)
        sys.exit(1)

    b64_str = api_data.get("data", "")
    if not b64_str:
        print("ERROR: API 返回数据中缺少 data 字段", file=sys.stderr)
        sys.exit(1)

    return base64.b64decode(b64_str)


def cmd_install(skill_name: str, api_url: str, skills_root: Path, script_path: Path) -> None:
    """Download .dat and install locally with metadata SKILL.md."""
    raw = download_raw(skill_name, api_url)
    meta = extract_metadata(raw)

    dest = skills_root / skill_name
    dest.mkdir(parents=True, exist_ok=True)

    # Save .dat
    dat_path = dest / "skill.dat"
    dat_path.write_bytes(raw)
    print(f"Saved .dat → {dat_path}", file=sys.stderr)

    # Write metadata SKILL.md
    name = meta.get("name", skill_name)
    description = meta.get("description", "")
    slug = meta.get("slug", skill_name)
    version = meta.get("version", "0.0.0")
    agent_created = meta.get("agent_created", "false")

    frontmatter = (
        f"---\n"
        f"name: {name}\n"
        f"slug: {slug}\n"
        f"version: {version}\n"
        f"description: \"{description}\"\n"
        f"agent_created: {agent_created}\n"
        f"encrypted: true\n"
        f"---\n"
    )
    usage = (
        f"# {name} (已加密安装)\n\n"
        f"此技能已加密安装在本地。完整内容需要解密后使用。\n\n"
        f"**解密命令：**\n"
        f"```bash\n"
        f"python {script_path} {slug} --local --skills-root {skills_root}\n"
        f"```\n\n"
        f"解密结果输出到 stdout，AI 捕获后仅存于上下文内存，不写入磁盘。\n"
    )
    sk_path = dest / "SKILL.md"
    sk_path.write_text(frontmatter + usage, encoding="utf-8")
    print(f"Saved metadata → {sk_path}", file=sys.stderr)
    print(f"Installed: {name} v{version}", file=sys.stderr)


def cmd_local(skill_name: str, key: bytes, skills_root: Path) -> None:
    """Decrypt a locally installed skill → stdout."""
    dat_path = skills_root / skill_name / "skill.dat"
    if not dat_path.exists():
        print(f"ERROR: 本地未安装 {skill_name}，请先 --install", file=sys.stderr)
        sys.exit(1)

    raw = dat_path.read_bytes()
    result = decrypt_dat(raw, key)
    print(result)


def cmd_fetch(skill_name: str, key: bytes, api_url: str) -> None:
    """Download + decrypt → stdout (one-shot, no local save)."""
    raw = download_raw(skill_name, api_url)
    result = decrypt_dat(raw, key)
    print(result)


def main():
    configure_console_encoding()

    ap = argparse.ArgumentParser(
        description="SkillHub encrypted skill: install / decrypt locally / one-shot fetch+decrypt"
    )
    ap.add_argument("skill_name", help="Skill slug (e.g. 'writepaper')")
    ap.add_argument("--skills-root", required=True, help="Skills installation directory (e.g. ~/.workbuddy/skills)")
    ap.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")

    group = ap.add_mutually_exclusive_group()
    group.add_argument("--install", action="store_true",
                      help="Download .dat + extract metadata SKILL.md (no decryption)")
    group.add_argument("--local", action="store_true",
                      help="Decrypt locally installed .dat → stdout")

    args = ap.parse_args()
    skills_root = Path(args.skills_root).resolve()
    script_path = Path(__file__).resolve()

    if args.install:
        cmd_install(args.skill_name, args.api_url, skills_root, script_path)
    elif args.local:
        key = resolve_key()
        cmd_local(args.skill_name, key, skills_root)
    else:
        key = resolve_key()
        cmd_fetch(args.skill_name, key, args.api_url)


if __name__ == "__main__":
    main()
