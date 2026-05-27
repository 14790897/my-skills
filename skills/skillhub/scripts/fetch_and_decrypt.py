"""
SkillHub encrypted skill downloader & decryptor — one-step command.

Usage:
    python fetch_and_decrypt.py <skill-name> [--key KEY] [--api-url URL]

Downloads the encrypted skill from the SkillHub API, base64-decodes the
response into binary .dat format, and decrypts it — outputting the full
SKILL.md to stdout.

Key priority: --key arg > SKILL_ENCRYPTION_KEY env var.
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


def decrypt_dat(raw: bytes, key: bytes) -> str:
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


def main():
    ap = argparse.ArgumentParser(
        description="Download and decrypt a SkillHub encrypted skill in one step"
    )
    ap.add_argument("skill_name", help="Skill slug (e.g. 'writepaper')")
    ap.add_argument("--key", help="64-char hex encryption key")
    ap.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    args = ap.parse_args()

    # Resolve key
    key_hex = args.key or os.environ.get("SKILL_ENCRYPTION_KEY", "") or "0322a06e6803ebcc8b96b9dc3221e1a2e49d399774c046b70014103f13084312"
    if not key_hex or len(key_hex) != 64:
        print(
            "ERROR: 需要 64 位 hex 密钥 (--key 或 SKILL_ENCRYPTION_KEY 环境变量)",
            file=sys.stderr,
        )
        sys.exit(1)
    key = bytes.fromhex(key_hex)

    # Download encrypted data from API
    url = f"{args.api_url.rstrip('/')}/{args.skill_name}/encrypted"
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

    # Base64 decode → binary .dat → decrypt
    raw = base64.b64decode(b64_str)
    result = decrypt_dat(raw, key)
    print(result)


if __name__ == "__main__":
    main()
