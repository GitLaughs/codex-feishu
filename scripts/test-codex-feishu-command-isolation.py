#!/usr/bin/env python3
"""Golden tests for codex-feishu workspace command isolation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def workspace_name(root: Path) -> str:
    data = json.loads((root / "workspace_manifest.json").read_text(encoding="utf-8-sig"))
    return str(data.get("workspace") or root.name)


def run(root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "codex-feishu-command.py"),
            "--root",
            str(root),
            *args,
        ],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fail(message: str, proc: subprocess.CompletedProcess | None = None) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    if proc is not None:
        print("stdout:", proc.stdout[:1000], file=sys.stderr)
        print("stderr:", proc.stderr[:1000], file=sys.stderr)
    raise SystemExit(1)


def assert_workspace_scope(root: Path) -> None:
    if not (root / "workspace_manifest.json").exists():
        fail(f"missing manifest: {root / 'workspace_manifest.json'}")
    marker = f"范围：{workspace_name(root)}"
    checks = [
        ("/files find", ("/files", "find", "guide")),
        ("/memfind", ("/memfind", "memory")),
        ("/memfind recent", ("/memfind", "recent", "3")),
        ("/files recent", ("/files", "recent", "3")),
        ("/files pending", ("/files", "pending")),
        ("/knowledge summary", ("/knowledge", "summary")),
        ("/knowledge search", ("/knowledge", "search", "Knowledge")),
        ("/tasks list", ("/tasks", "list")),
        ("/workspace-info", ("/workspace-info",)),
    ]
    for label, args in checks:
        proc = run(root, root, *args)
        if proc.returncode not in {0, 1}:
            fail(f"{label} failed", proc)
        if marker not in proc.stdout:
            fail(f"{label} did not scope to workspace", proc)


def assert_query_redaction(root: Path) -> None:
    sentinel = f"CODEX_FEISHU_SECRET_SENTINEL_{int(time.time())}"
    proc = run(root, root, "/memfind", sentinel)
    if proc.returncode != 0:
        fail("redaction sentinel query failed", proc)
    today = root / "runs" / f"{time.strftime('%Y-%m-%d', time.localtime())}.jsonl"
    if not today.exists():
        fail(f"missing run log: {today}")
    text = today.read_text(encoding="utf-8", errors="replace")
    if sentinel in text:
        fail("raw query text leaked into run log")
    rows = []
    for line in text.splitlines()[-80:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    recent = [row for row in rows if row.get("tool") in {"codex-feishu-command", "codex-feishu-index"}]
    if not recent:
        fail("no recent redacted command/index run found")
    if not any(isinstance(row.get("body"), dict) or isinstance(row.get("query"), dict) for row in recent):
        fail("recent run did not record query/body fingerprint metadata")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="codex-feishu command isolation golden tests")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    assert_workspace_scope(root)
    assert_query_redaction(root)
    print("codex-feishu-command isolation tests ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
