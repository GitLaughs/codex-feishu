#!/usr/bin/env python3
"""Tests for cc-connect lark-events hook capture."""

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


def run_hook(root: Path, project: str, text: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "CODEX_FEISHU_ROOT": str(root),
            "CODEX_FEISHU_LARK_EVENT_WORKSPACE_MAP": '{"group-bot":"project-group"}',
            "CC_HOOK_EVENT": "message.received",
            "CC_HOOK_PROJECT": project,
            "CC_HOOK_TIMESTAMP": "2026-05-24T12:34:56+08:00",
            "CC_HOOK_PLATFORM": "feishu",
            "CC_HOOK_USER_ID": "ou_secret_raw_id",
            "CC_HOOK_USER_NAME": "测试成员",
            "CC_HOOK_SESSION_KEY": "feishu:raw-session-key",
            "CC_HOOK_CONTENT": text,
            "CODEX_FEISHU_LARK_EVENT_HOOK_VERBOSE": "1",
        }
    )
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("cc-connect-lark-events-hook.py"))],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)


def main() -> int:
    root = Path.cwd() / ".tmp" / f"lark-events-hook-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    root.mkdir(parents=True, exist_ok=True)

    run_hook(root, "group-bot", "模型训练今天推进，api_key=mock-secret-value")
    event_path = root / "project-group" / "memory" / "lark-events" / "2026-05-24.ndjson"
    event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
    text = json.dumps(event, ensure_ascii=False)
    if event["project"] != "group-bot" or event["text"].count("[REDACTED]") != 1:
        raise SystemExit("captured event did not preserve project or redact secret")
    if "ou_secret_raw_id" in text or "raw-session-key" in text:
        raise SystemExit("captured event leaked raw ids")

    event_path.write_text(event_path.read_text(encoding="utf-8") + ("x" * 1400) + "\n", encoding="utf-8")
    env_max = os.environ.copy()
    env_max["CODEX_FEISHU_LARK_EVENTS_MAX_BYTES"] = "1024"
    old_env = os.environ.get("CODEX_FEISHU_LARK_EVENTS_MAX_BYTES")
    os.environ["CODEX_FEISHU_LARK_EVENTS_MAX_BYTES"] = "1024"
    run_hook(root, "group-bot", "第二条模型训练消息")
    if old_env is None:
        os.environ.pop("CODEX_FEISHU_LARK_EVENTS_MAX_BYTES", None)
    else:
        os.environ["CODEX_FEISHU_LARK_EVENTS_MAX_BYTES"] = old_env
    rotated_path = root / "project-group" / "memory" / "lark-events" / "2026-05-24-001.ndjson"
    if not rotated_path.exists():
        raise SystemExit("lark-events did not rotate to a new ndjson shard")

    run_hook(root, "private-bot", "私聊不应该进入群事件")
    private_matches = list(root.glob("*/memory/lark-events/*.ndjson"))
    if len(private_matches) != 2:
        raise SystemExit("private or unknown project wrote lark-events unexpectedly")

    group_script = Path.cwd() / "scripts" / "codex-feishu-group-sense.py"
    proc = subprocess.run(
        [sys.executable, str(group_script), "--workspace", str(root / "project-group"), "--recent-limit", "3"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)
    if "messages=" not in proc.stdout or "topics_added=" not in proc.stdout:
        raise SystemExit(f"group-sense did not consume captured lark event\n{proc.stdout}")

    print("cc_connect_lark_events_hook_tests=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

