#!/usr/bin/env python3
"""Tests for Python private-message capture hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def run_capture(root: Path, project: str, text: str, verbose: bool = True) -> str:
    env = os.environ.copy()
    env.update(
        {
            "CODEX_FEISHU_ROOT": str(root),
            "CODEX_FEISHU_PRIVATE_CAPTURE_PROJECTS": "private-bot",
            "CC_HOOK_EVENT": "message.received",
            "CC_HOOK_PROJECT": project,
            "CC_HOOK_TIMESTAMP": "2026-05-24T12:34:56+08:00",
            "CC_HOOK_SESSION_KEY": "raw-private-session",
            "CC_HOOK_USER_ID": "ou_raw_private_id",
            "CC_HOOK_USER_NAME": "测试用户",
            "CC_HOOK_CONTENT": text,
        }
    )
    if verbose:
        env["CODEX_FEISHU_PRIVATE_CAPTURE_VERBOSE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(Path.cwd() / "scripts" / "capture-private-message.py")],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)
    return proc.stdout


def inbox_lines(root: Path) -> list[str]:
    inbox = root / "memory" / "inbox"
    lines: list[str] = []
    for path in sorted(inbox.glob("2026-05-24-private-messages*.jsonl")):
        lines.extend(path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line.strip() and line.lstrip().startswith("{")]


def main() -> int:
    root = Path.cwd() / ".tmp" / f"capture-private-py-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    root.mkdir(parents=True, exist_ok=True)

    out = run_capture(root, "private-bot", "我准备下周把报告整理完 api_key=private-secret-value")
    if '"ok": true' not in out:
        raise SystemExit(f"private capture failed: {out}")

    inbox_path = root / "memory" / "inbox" / "2026-05-24-private-messages.jsonl"
    entry = json.loads(inbox_path.read_text(encoding="utf-8").splitlines()[0])
    rendered = json.dumps(entry, ensure_ascii=False)
    if entry["semantic_category"] != "intent" or entry["importance"] < 3:
        raise SystemExit(f"private capture did not classify intent: {entry}")
    if "private-secret-value" in rendered or "raw-private-session" in rendered or "ou_raw_private_id" in rendered:
        raise SystemExit("private capture leaked secret or raw ids")
    if "[REDACTED]" not in rendered or not entry.get("session_hash") or not entry.get("user_id_hash"):
        raise SystemExit("private capture did not redact or hash ids")

    daily = (root / "memory" / "daily" / "2026-05-24.md").read_text(encoding="utf-8")
    if "准备下周" not in daily or "private-secret-value" in daily:
        raise SystemExit("important private capture not written to daily or leaked secret")

    inbox_path.write_text(inbox_path.read_text(encoding="utf-8") + ("x" * 1400) + "\n", encoding="utf-8")
    old_max = os.environ.get("CODEX_FEISHU_PRIVATE_INBOX_MAX_BYTES")
    os.environ["CODEX_FEISHU_PRIVATE_INBOX_MAX_BYTES"] = "1024"
    run_capture(root, "private-bot", "明天提醒我检查分片 inbox")
    if old_max is None:
        os.environ.pop("CODEX_FEISHU_PRIVATE_INBOX_MAX_BYTES", None)
    else:
        os.environ["CODEX_FEISHU_PRIVATE_INBOX_MAX_BYTES"] = old_max
    rotated_inbox = root / "memory" / "inbox" / "2026-05-24-private-messages-001.jsonl"
    if not rotated_inbox.exists():
        raise SystemExit("private capture did not rotate to a new jsonl shard")

    run_capture(root, "other-bot", "群消息不该进入私聊 inbox")
    if len(inbox_lines(root)) != 2:
        raise SystemExit("group project was captured as private")

    run_capture(root, "private-bot", "ok")
    if len(inbox_lines(root)) != 2:
        raise SystemExit("noise message was captured")

    curator_out = subprocess.run(
        [
            sys.executable,
            str(Path.cwd() / "scripts" / "memory-curator.py"),
            "--workspace",
            str(root),
            "--date",
            "2026-05-24",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if curator_out.returncode != 0:
        raise SystemExit(curator_out.stdout + curator_out.stderr)
    intentions = (root / "memory" / "facts" / "intentions.md").read_text(encoding="utf-8")
    tasks = (root / "memory" / "tasks" / "open.md").read_text(encoding="utf-8")
    if "准备下周" not in intentions or "检查分片 inbox" not in tasks or "private-secret-value" in intentions + tasks:
        raise SystemExit("curator did not consume captured private inbox safely")

    print("capture_private_message_py_tests=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

