"""
skill_decrypt_mcp — MCP Server for decrypting SkillHub encrypted skills.

Only one tool: decrypt_base64 — receives base64-encoded .dat content,
decrypts with AES-256-GCM, returns plaintext to AI (never writes to disk).

Key is read from SKILL_ENCRYPTION_KEY environment variable.
The user never sees the skill content; only the AI does.

.dat format:
    [4B LE: metadata_json_len] [metadata JSON] [nonce(12) + encrypted_body + tag(16)]

Metadata is plaintext — only the body is encrypted.

Usage:
    SKILL_ENCRYPTION_KEY=xxx python skill_decrypt_mcp.py

MCP config (mcp.json):
    "skill-decrypt": {
        "command": "python",
        "args": ["C:/git-program/my-skills-hub/skill_decrypt_mcp.py"],
        "env": { "SKILL_ENCRYPTION_KEY": "xxx" }
    }
"""

from __future__ import annotations

import base64
import json
import os
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = (
    "Skill decryption service. Use decrypt_base64 to decode encrypted .dat content "
    "into plaintext Markdown. The key is stored server-side via SKILL_ENCRYPTION_KEY. "
    "Only the AI sees the decrypted output — plaintext never touches the user's filesystem. "
    "Metadata (name, description) is plaintext inside the .dat; only the body is encrypted."
)

mcp = FastMCP(name="skill-decrypt", instructions=_INSTRUCTIONS)


def _get_key() -> bytes:
    key_hex = os.environ.get("SKILL_ENCRYPTION_KEY", "")
    if not key_hex:
        raise ValueError("SKILL_ENCRYPTION_KEY environment variable is not set")
    if len(key_hex) != 64:
        raise ValueError(f"SKILL_ENCRYPTION_KEY must be 64 hex chars, got {len(key_hex)}")
    return bytes.fromhex(key_hex)


def _metadata_to_yaml(metadata: dict) -> str:
    """Convert a flat metadata dict to YAML frontmatter."""
    lines = ["---"]
    for k, v in metadata.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


@mcp.tool()
def decrypt_base64(data_b64: str) -> str:
    """
    Decrypt a base64-encoded .dat file and return the full SKILL.md content.

    The .dat format:
      [4B LE length of metadata JSON] [metadata JSON (plaintext)]
      [12B nonce] [encrypted body + 16B auth tag]

    Metadata is NOT encrypted — only the skill body is.
    The output is a complete Markdown string with YAML frontmatter.

    Args:
        data_b64: Base64-encoded encrypted .dat file content.

    Returns:
        Full SKILL.md content (Markdown string with frontmatter + body).
        The plaintext stays in AI memory — it is NEVER written to disk.
    """
    try:
        key = _get_key()
    except ValueError as e:
        return f"[ERROR] Key configuration issue: {e}"

    aesgcm = AESGCM(key)

    try:
        raw = base64.b64decode(data_b64)
    except Exception as e:
        return f"[ERROR] Invalid base64 input: {e}"

    # Parse metadata header
    if len(raw) < 5:
        return "[ERROR] Invalid .dat data: too short"

    meta_len = struct.unpack("<I", raw[:4])[0]
    meta_bytes = raw[4:4 + meta_len]
    remainder = raw[4 + meta_len:]

    if len(remainder) < 13:
        return "[ERROR] Invalid .dat data: insufficient ciphertext"

    # Parse metadata
    try:
        metadata = json.loads(meta_bytes.decode("utf-8"))
    except Exception as e:
        return f"[ERROR] Failed to parse metadata: {e}"

    # Decrypt body
    nonce = remainder[:12]
    ciphertext = remainder[12:]

    try:
        body = aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception as e:
        return f"[ERROR] Decryption failed: {e}"

    # Reconstruct full SKILL.md
    yaml_header = _metadata_to_yaml(metadata)
    return yaml_header + body


if __name__ == "__main__":
    mcp.run(transport="stdio")
