#!/usr/bin/env python3
"""Smoke tests for Feishu private/group/recall evidence packets."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)
    return proc.stdout


def assert_clean_packet(text: str, label: str) -> None:
    for needle in ('"text"', '"message_id"', "message_id", "api_key=", "secret-value", "ou_raw", "om_raw", "{", "}"):
        if needle in text:
            raise SystemExit(f"{label} leaked {needle!r}")


def main() -> int:
    root = Path.cwd().resolve()
    test_root = root / ".tmp" / f"feishu-evidence-packets-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    workspace = test_root
    memory = workspace / "memory"
    inbox = memory / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (memory / "daily").mkdir(parents=True, exist_ok=True)
    (memory / "facts").mkdir(parents=True, exist_ok=True)
    (memory / "search").mkdir(parents=True, exist_ok=True)

    date_text = "2026-05-24"
    private_lines = [
        {"time": "09:00:00", "user": "测试用户", "semantic_category": "intent", "text": "我准备明天整理飞书证据包 api_key=secret-value"},
        {"time": "09:05:00", "user": "测试用户", "semantic_category": "task", "text": "提醒我检查 memory recall 输出"},
    ]
    (inbox / f"{date_text}-private-messages.jsonl").write_text(
        json.dumps(private_lines[0], ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (inbox / f"{date_text}-private-messages-001.jsonl").write_text(
        json.dumps(private_lines[1], ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (memory / "facts" / "intentions.md").write_text(
        "# Intentions\n\n- [09:00:00] [intent/4] [inbox] 明天整理飞书证据包 <!-- source:test -->\n",
        encoding="utf-8",
    )

    private_packet = workspace / "private-packet.md"
    out = run(
        [
            sys.executable,
            str(root / "scripts" / "build-feishu-private-packet.py"),
            "--workspace",
            str(workspace),
            "--date",
            date_text,
            "--output",
            str(private_packet),
        ]
    )
    if "private_packet=" not in out:
        raise SystemExit("private packet output missing")
    private_text = private_packet.read_text(encoding="utf-8")
    if "整理飞书证据包" not in private_text or "memory recall" not in private_text:
        raise SystemExit("private packet did not include both shards")
    assert_clean_packet(private_text, "private packet")

    group = test_root / "project-group"
    event_dir = group / "memory" / "lark-events"
    event_dir.mkdir(parents=True, exist_ok=True)
    (group / "local_files").mkdir(parents=True, exist_ok=True)
    (group / "KNOWLEDGE.md").write_text("# Knowledge\n\n- 当前原型路线采用双 head。\n", encoding="utf-8")
    (group / "local_files" / "INDEX.md").write_text("# Index\n\n- `local_files/docs/report.md` 报告摘要。\n", encoding="utf-8")
    content = json.dumps({"text": "小王负责报告提交，om_raw_should_hide"}, ensure_ascii=False)
    event = {"time": "2026-05-24T10:00:00+08:00", "sender": {"name": "小王"}, "event": {"message": {"content": content}}}
    (event_dir / "2026-05-24.ndjson").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    group_packet = group / "group-packet.md"
    out = run(
        [
            sys.executable,
            str(root / "scripts" / "build-feishu-group-packet.py"),
            "--workspace",
            str(group),
            "--output",
            str(group_packet),
        ]
    )
    if "group_packet=" not in out:
        raise SystemExit("group packet output missing")
    group_text = group_packet.read_text(encoding="utf-8")
    if "小王负责报告提交" not in group_text or "报告摘要" not in group_text:
        raise SystemExit("group packet did not include event and file index")
    assert_clean_packet(group_text, "group packet")

    metadata_dir = group / "local_files" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "file_abc123.json").write_text(
        json.dumps(
            {
                "id": "file_abc123",
                "workspace": "project-group",
                "path": "local_files/docs/report.md",
                "name": "report.md",
                "summary": "报告元数据摘要",
                "status": "indexed",
                "size_bytes": 12,
                "sha256": "a" * 64,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run(
        [
            sys.executable,
            str(root / "scripts" / "build-feishu-group-packet.py"),
            "--workspace",
            str(group),
            "--output",
            str(group_packet),
        ]
    )
    group_text = group_packet.read_text(encoding="utf-8")
    if "报告元数据摘要" not in group_text or "file-metadata" not in group_text:
        raise SystemExit("group packet did not include file metadata")

    (memory / "search" / "index.jsonl").write_text(
        json.dumps({"kind": "memory_line", "path": "memory/facts/intentions.md", "line": 3, "text": "明天整理飞书证据包 api_key=secret-value"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    recall_out = run(
        [
            sys.executable,
            str(root / "scripts" / "build-feishu-recall-packet.py"),
            "--workspace",
            str(workspace),
            "--query",
            "飞书 证据包",
        ]
    )
    if "字段顺序：分数 | 来源 | 行 | 内容" not in recall_out or "飞书证据包" not in recall_out:
        raise SystemExit("recall packet did not return compact result")
    assert_clean_packet(recall_out, "recall packet")

    ps_recall = run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / "scripts" / "memory-recall.ps1"),
            "-Workspace",
            str(workspace),
            "-Query",
            "飞书 证据包",
        ]
    )
    if "字段顺序：分数 | 来源 | 行 | 内容" not in ps_recall:
        raise SystemExit("memory-recall.ps1 did not use compact packet builder")

    print("feishu_evidence_packets_tests=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

