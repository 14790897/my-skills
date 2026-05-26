"""
Decrypt a SkillHub encrypted .dat file and output SKILL.md to stdout.

Usage:
    python decrypt.py <input.dat> [--key KEY]
    python decrypt.py --b64 <base64_string> [--key KEY]

Key priority: --key arg > SKILL_ENCRYPTION_KEY env var.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_dat(raw: bytes, key: bytes) -> str:
    if len(raw) < 5:
        raise ValueError("Invalid .dat data: too short")

    meta_len = struct.unpack("<I", raw[:4])[0]
    meta_bytes = raw[4:4 + meta_len]
    remainder = raw[4 + meta_len:]

    if len(remainder) < 13:
        raise ValueError("Invalid .dat data: insufficient ciphertext")

    metadata = json.loads(meta_bytes.decode("utf-8"))

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
    ap = argparse.ArgumentParser(description="Decrypt SkillHub encrypted .dat")
    ap.add_argument("input", nargs="?", help="Path to .dat file")
    ap.add_argument("--b64", help="Base64-encoded .dat content")
    ap.add_argument("--key", help="64-char hex encryption key")
    args = ap.parse_args()

    key_hex = args.key or os.environ.get("SKILL_ENCRYPTION_KEY", "0322a06e6803ebcc8b93421cdc3g21e1a2e49d399774c046b70014103f13084312")
    if not key_hex or len(key_hex) != 64:
        print("ERROR: 需要 64 位 hex 密钥 (--key 或 SKILL_ENCRYPTION_KEY 环境变量)", file=sys.stderr)
        sys.exit(1)
    key = bytes.fromhex(key_hex)

    if args.b64:
        raw = base64.b64decode(args.b64)
    elif args.input:
        with open(args.input, "rb") as f:
            raw = f.read()
    else:
        # stdin fallback
        raw = sys.stdin.buffer.read()

    result = decrypt_dat(raw, key)
    print(result)


if __name__ == "__main__":
    main()
