#!/usr/bin/env python3
"""Reject sensitive paths and content in every Git-index blob, without printing values."""

from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path
import re
import subprocess
import sys


DENIED_DIRECTORIES = frozenset(
    {
        ".aws", ".azure", ".gcp", ".ssh", ".neurocore", "credentials", "secrets",
        "instance", "instances", "user_data", "user-data", "userdata", "user_instances",
        "user-instances", "data", "runtime", "database", "databases", "db", "log", "logs",
        "cache", "caches", ".cache", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", ".venv", "venv", ".tox", ".nox", "backup", "backups", "output",
        "outputs", "export", "exports", "chat_exports", "chat-exports", "node_modules",
        "build", "dist", ".wheel-venv", "tmp", ".tmp", "temp", "verification",
        "local-assets", "generated-assets",
    }
)
DENIED_FILENAMES = (
    ".env", ".env.*", "*.env", "credentials*", "secrets*", "id_rsa*", "id_ed25519*",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", "*.db", "*.db-*",
    "*.sqlite", "*.sqlite3", "*.sqlite-*", "*.sqlite3-*", "*.log", "*.log.*", "*.bak",
    "*.backup", "*.old", "*.orig", "*.swp", "*.tmp", "*.dump", "*.dump.sql",
    "chat*.json", "conversation*.json", "messages*.json", "history*.json",
    "chat*.jsonl", "conversation*.jsonl", "messages*.jsonl", "history*.jsonl",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.bmp", "*.tiff",
    "*.mp4", "*.mov", "*.webm", "*.mp3", "*.wav", "*.ogg", "*.flac", "*.glb",
    "*.gltf", "*.blend", "*.fbx", "*.obj", "*.psd", "*.safetensors", "*.pt", "*.pth",
    "*.zip", "*.7z", "*.tar", "*.gz", "*.bz2", "*.xz", "*.pdf", "*.docx", "*.xlsx",
    "*.svg", "*.onnx", "*.gguf", "*.bin",
)
CONTENT_RULES = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("service-secret-key", re.compile(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|(?:sk|rk)_live_[A-Za-z0-9]{16,})\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.I)),
)
# Paths may embed a complete credential next to letters, underscores or Unicode.
# Reuse each core and its flags, removing only explicit outer word boundaries.
# Keep CONTENT_RULES unchanged: prose still uses its original matching semantics.
PATH_RULES = tuple(
    (name, re.compile(pattern.pattern.removeprefix(r"\b").removesuffix(r"\b"), pattern.flags))
    for name, pattern in CONTENT_RULES
)
ASSIGNMENT = re.compile(
    r"(?<![\w-])['\"]?(?:[A-Za-z][\w.-]*[_-])?"
    r"(?:api[_-]?key|access[_-]?key(?:[_-]?id)?|secret(?:[_-]?key)?|token|password|passwd|pwd|client[_-]?secret|private[_-]?key)"
    r"['\"]?\s*(?:=|:)\s*"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;#}\]]+)",
    re.I,
)
PLACEHOLDERS = frozenset(
    {"", "example", "example_value", "replace_me", "replace-me", "your_api_key", "redacted", "changeme"}
)
MAX_BLOB_BYTES = 4 * 1024 * 1024


def git(repo: Path, *args: str) -> bytes:
    """Do not forward Git stderr: diagnostics can contain untrusted file content."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("git-operation-failed")
    return result.stdout


def safe_placeholder(raw: str) -> bool:
    value = raw[1:-1] if raw[:1] in {"'", '"'} and raw[-1:] == raw[:1] else raw
    if value.lower() in PLACEHOLDERS or re.fullmatch(r"<[A-Z][A-Z0-9_ -]*>", value):
        return True
    if re.fullmatch(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})", value):
        return True
    # These unquoted expressions reference runtime configuration, not stored values.
    return raw[:1] not in {"'", '"'} and (
        raw in {"None", "null", "True", "False", "..."}
        or raw.startswith(("os.environ[", "os.environ.get(", "os.getenv(", "getenv(", "process.env."))
    )


def content_violations(blob: bytes) -> set[str]:
    if len(blob) > MAX_BLOB_BYTES:
        return {"oversized-blob"}
    if any(byte < 32 and byte not in (9, 10, 13) or byte == 127 for byte in blob):
        return {"binary-content"}
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"non-utf8-content"}
    rules = {name for name, pattern in CONTENT_RULES if pattern.search(text)}
    if any(not safe_placeholder(match["value"]) for match in ASSIGNMENT.finditer(text)):
        rules.add("credential-assignment")
    return rules


def path_violations(raw_path: bytes) -> set[str]:
    rules = content_violations(raw_path)
    if rules & {"oversized-blob", "binary-content", "non-utf8-content"}:
        return rules
    text = raw_path.decode("utf-8-sig")
    return rules | {name for name, pattern in PATH_RULES if pattern.search(text)}


def scan(repo: Path) -> list[tuple[int, str]]:
    # Findings never retain paths: filenames can contain the secrets we detect.
    findings: set[tuple[int, str]] = set()
    # --stage reports blob IDs from the index, even when the working tree differs.
    entries = git(repo, "ls-files", "--stage", "-z").split(b"\0")
    for file_number, entry in enumerate(filter(None, entries), start=1):
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            findings.add((file_number, "unreadable-index-entry"))
            continue
        for rule in path_violations(raw_path):
            findings.add((file_number, "path-" + rule))
        parts = path.lower().split("/")
        if any(part in DENIED_DIRECTORIES for part in parts[:-1]):
            findings.add((file_number, "denied-directory"))
        if any(fnmatch.fnmatchcase(parts[-1], pattern) for pattern in DENIED_FILENAMES):
            findings.add((file_number, "denied-filename"))
        if stage != "0":
            findings.add((file_number, "unmerged-index-entry"))
        if mode not in {"100644", "100755"}:
            findings.add((file_number, "unsupported-index-mode"))
            continue
        try:
            # Check size before materializing the blob in memory.
            size = int(git(repo, "cat-file", "-s", oid))
            if size > MAX_BLOB_BYTES:
                findings.add((file_number, "oversized-blob"))
                continue
            blob = git(repo, "cat-file", "blob", oid)
            for rule in content_violations(blob):
                findings.add((file_number, rule))
        except (OSError, RuntimeError, ValueError):
            findings.add((file_number, "unreadable-blob"))
    return sorted(findings)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error includes untrusted argument values.
        self.exit(2, "Sensitive-file check failed: invalid-arguments\n")


def main() -> int:
    parser = SafeArgumentParser(prog="check_sensitive.py", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."), help="Git working tree (default: current directory)")
    args = parser.parse_args()
    try:
        findings = scan(args.repo)
    except (OSError, RuntimeError, ValueError):
        print("Sensitive-file check failed: git-index-unavailable", file=sys.stderr)
        return 2
    for file_number, rule in findings:
        print(f"file#{file_number}: {rule}", file=sys.stderr)
    if findings:
        print(f"Sensitive-file check failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print("Sensitive-file check passed: all Git-index entries checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
