#!/usr/bin/env python3
"""Redact raw query text from codex-feishu runs/*.jsonl audit logs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any


def text_fingerprint(text: str) -> dict[str, Any]:
    raw = text.encode("utf-8", errors="replace")
    return {
        "len": len(text),
        "sha256_12": hashlib.sha256(raw).hexdigest()[:12],
    }


def redacted_argv(argv: list[Any]) -> tuple[list[Any], int]:
    changed = 0
    cleaned: list[Any] = []
    redact_next = False
    for item in argv:
        if redact_next and isinstance(item, str):
            if not item.startswith("<query "):
                meta = text_fingerprint(item)
                cleaned.append(f"<query len={meta['len']} sha256_12={meta['sha256_12']}>")
                changed += 1
            else:
                cleaned.append(item)
            redact_next = False
            continue
        cleaned.append(item)
        if item == "search":
            redact_next = True
    return cleaned, changed


def redact_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    changed = 0
    item = dict(payload)
    for key in ("body", "query"):
        value = item.get(key)
        if isinstance(value, str):
            item[key] = text_fingerprint(value)
            changed += 1
    argv = item.get("argv")
    if isinstance(argv, list):
        redacted, n = redacted_argv(argv)
        item["argv"] = redacted
        changed += n
    return item, changed


def redact_file(path: Path, apply: bool, backup_suffix: str) -> tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    changed_lines = 0
    changed_fields = 0
    for line in lines:
        if not line.strip():
            out.append(line)
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if not isinstance(payload, dict):
            out.append(line)
            continue
        redacted, n = redact_payload(payload)
        if n:
            changed_lines += 1
            changed_fields += n
        out.append(json.dumps(redacted, ensure_ascii=False, separators=(",", ":")))
    if apply and changed_lines:
        backup = path.with_name(path.name + backup_suffix)
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed_lines, changed_fields


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redact codex-feishu runs/*.jsonl logs")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--apply", action="store_true", help="rewrite logs after creating .bak backup")
    parser.add_argument("--backup-suffix", default=f".bak-{time.strftime('%Y%m%d%H%M%S')}")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    runs = root / "runs"
    if not runs.exists():
        print("runs=missing changed_lines=0 changed_fields=0")
        return 0
    total_lines = 0
    total_fields = 0
    files = sorted(path for path in runs.glob("*.jsonl") if path.is_file())
    for path in files:
        changed_lines, changed_fields = redact_file(path, args.apply, args.backup_suffix)
        total_lines += changed_lines
        total_fields += changed_fields
        if changed_lines:
            action = "redacted" if args.apply else "would_redact"
            print(f"{action} file={path} lines={changed_lines} fields={changed_fields}")
    print(f"runs_redaction apply={str(args.apply).lower()} files={len(files)} changed_lines={total_lines} changed_fields={total_fields}")
    return 1 if total_lines and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
