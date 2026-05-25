#!/usr/bin/env python3
"""Capture cc-connect group message hooks into group lark-events logs."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_WORKSPACES: dict[str, str] = {}

SECRET_PATTERNS = [
    re.compile(r"(?i)[\"']?(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}\]\)]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]

DEFAULT_MAX_JSONL_BYTES = 5 * 1024 * 1024


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", redact(value)).strip()


def env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def workspace_map() -> dict[str, str]:
    mapping = dict(PROJECT_WORKSPACES)
    raw = os.environ.get("CODEX_FEISHU_LARK_EVENT_WORKSPACE_MAP") or os.environ.get("CODEX_FEISHU_PROJECT_WORKSPACE_MAP", "")
    if not raw:
        return mapping
    try:
        data = json.loads(raw)
    except Exception:
        return mapping
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                mapping[key.strip()] = value.strip()
    return mapping


def max_jsonl_bytes() -> int:
    raw = os.environ.get("CODEX_FEISHU_LARK_EVENTS_MAX_BYTES", "")
    if not raw:
        return DEFAULT_MAX_JSONL_BYTES
    try:
        return max(1024, int(raw))
    except ValueError:
        return DEFAULT_MAX_JSONL_BYTES


def rotating_jsonl_path(directory: Path, stem: str, suffix: str, next_line: str, max_bytes: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"{stem}{suffix}"
    candidates = [base] + sorted(directory.glob(f"{stem}-[0-9][0-9][0-9]{suffix}"))
    encoded_len = len(next_line.encode("utf-8"))
    for path in candidates:
        if not path.exists():
            return path
        try:
            if path.stat().st_size + encoded_len <= max_bytes:
                return path
        except OSError:
            continue
    return directory / f"{stem}-{len(candidates):03d}{suffix}"


def capture() -> tuple[bool, str]:
    if os.environ.get("CC_HOOK_EVENT", "") != "message.received":
        return False, "ignored_event"

    project = os.environ.get("CC_HOOK_PROJECT", "")
    rel_workspace = workspace_map().get(project)
    if not rel_workspace:
        return False, "ignored_project"

    text = clean_text(env_first("CC_HOOK_TEXT", "CC_HOOK_CONTENT", "CC_HOOK_MESSAGE_TEXT", "CC_HOOK_MESSAGE"))
    if not text:
        return False, "empty_text"

    root = Path(os.environ.get("CODEX_FEISHU_ROOT", "/opt/codex-feishu")).resolve()
    workspace = (root / rel_workspace).resolve()
    try:
        workspace.relative_to(root)
    except ValueError:
        return False, "workspace_outside_root"

    timestamp = os.environ.get("CC_HOOK_TIMESTAMP", "") or dt.datetime.now().astimezone().isoformat()
    try:
        day = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        day = dt.date.today().isoformat()

    user_id = env_first("CC_HOOK_USER_ID", "CC_HOOK_SENDER_ID", "CC_HOOK_OPEN_ID", "CC_HOOK_USER_OPEN_ID")
    session_key = os.environ.get("CC_HOOK_SESSION_KEY", "")
    payload = {
        "time": timestamp,
        "source": "cc-connect-hook",
        "project": project,
        "platform": os.environ.get("CC_HOOK_PLATFORM", ""),
        "sender": {
            "name": clean_text(env_first("CC_HOOK_USER_NAME", "CC_HOOK_SENDER_NAME", "CC_HOOK_NAME")) or "unknown",
            "id_hash": stable_hash(user_id) if user_id else "",
        },
        "session_key_hash": stable_hash(session_key) if session_key else "",
        "text": text,
    }

    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    path = rotating_jsonl_path(workspace / "memory" / "lark-events", day, ".ndjson", line, max_jsonl_bytes())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return True, str(path)


def main() -> int:
    ok, detail = capture()
    if os.environ.get("CODEX_FEISHU_LARK_EVENT_HOOK_VERBOSE") == "1":
        print(json.dumps({"ok": ok, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

