#!/usr/bin/env python3
"""Format codex-feishu workspace health checks for chat commands."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


CHECKS = [
    ("manifest_health", "codex-feishu-manifest-health.py"),
    ("help_health", "codex-feishu-help-health.py"),
    ("file_health", "codex-feishu-file-health.py"),
    ("memory_health", "codex-feishu-memory-health.py"),
    ("runs_redaction", "codex-feishu-redact-runs.py"),
]


def run_check(root: Path, script_name: str) -> tuple[bool, str]:
    script = root / "scripts" / script_name
    if not script.exists():
        script = Path(__file__).resolve().with_name(script_name)
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    raw = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
    return proc.returncode == 0, (raw[-1] if raw else "")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="codex-feishu health command")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    results = []
    for name, script_name in CHECKS:
        ok, detail = run_check(root, script_name)
        results.append((name, ok, detail))
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    lines = [
        f"codex-feishu 健康：{'OK' if failed == 0 else 'FAIL'}",
        f"checks={passed} ok / {failed} fail",
    ]
    for name, ok, detail in results:
        lines.append(f"{name}={'ok' if ok else 'fail'}")
        if detail and not ok:
            lines.append(f"  {detail[:180]}")
    print("\n".join(lines)[:1800])
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
