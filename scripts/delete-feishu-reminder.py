#!/usr/bin/env python3
"""Delete a known Feishu calendar reminder created for an codex-feishu group."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml"}
SKIP_DIRS = {".git", ".cc-connect", ".tmp", "__pycache__", "code", "node_modules"}


def lark_cli() -> list[str]:
    override = os.environ.get("CODEX_FEISHU_LARK_CLI_BIN", "").strip()
    if override:
        return [override]

    command = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or shutil.which("lark-cli.ps1")
    if not command:
        raise RuntimeError("lark-cli not found in PATH.")
    return [command]


def run_json(argv: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        detail = (proc.stderr or output or f"exit code {proc.returncode}").strip()
        raise RuntimeError(detail)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        marker = output.find("{")
        if marker >= 0:
            try:
                return json.loads(output[marker:])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"lark-cli returned non-JSON output: {output[:500]}") from exc


def resolve_workspace(value: str) -> Path:
    workspace = Path(value).expanduser()
    if not workspace.is_absolute():
        workspace = ROOT / workspace
    workspace = workspace.resolve()
    try:
        workspace.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"workspace must stay under {ROOT}") from exc
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace does not exist: {workspace}")
    return workspace


def iter_known_files(workspace: Path):
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(workspace).parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        yield path


def event_id_is_known(workspace: Path, event_id: str) -> tuple[bool, str]:
    for path in iter_known_files(workspace):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if event_id in text:
            return True, str(path.relative_to(workspace))
    return False, ""


def validate_event_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,256}", value):
        raise ValueError("event_id contains unsupported characters")
    return value


def delete_event(args: argparse.Namespace) -> dict[str, Any]:
    event_id = validate_event_id(args.event_id)
    workspace = resolve_workspace(args.workspace)
    if args.require_known:
        known, source = event_id_is_known(workspace, event_id)
        if not known:
            raise RuntimeError(
                "refusing to delete an unknown calendar event_id; "
                "record it in this group workspace first or pass --no-require-known from a trusted main session"
            )
    else:
        source = ""

    params = {
        "calendar_id": args.calendar_id,
        "event_id": event_id,
        "need_notification": "true" if args.need_notification else "false",
    }
    argv = [
        *lark_cli(),
        "calendar",
        "events",
        "delete",
        "--as",
        "user",
        "--params",
        json.dumps(params, ensure_ascii=False, separators=(",", ":")),
    ]
    if not args.execute:
        argv.append("--dry-run")

    result = run_json(argv)
    return {
        "ok": True,
        "dry_run": not args.execute,
        "calendar_id": args.calendar_id,
        "event_id": event_id,
        "known_source": source,
        "need_notification": bool(args.need_notification),
        "result": result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete a known codex-feishu group Feishu calendar reminder.")
    parser.add_argument("--workspace", required=True, help="Group workspace path.")
    parser.add_argument("--event-id", required=True, help="Known Feishu calendar event_id.")
    parser.add_argument("--calendar-id", default=os.environ.get("FEISHU_CALENDAR_ID", "primary"), help="Calendar id. Default: primary.")
    parser.add_argument("--execute", action="store_true", help="Actually delete the event. Default is dry-run only.")
    parser.add_argument("--no-require-known", dest="require_known", action="store_false", help="Trusted main-session override.")
    parser.set_defaults(require_known=True)
    parser.add_argument("--no-notification", dest="need_notification", action="store_false", help="Do not notify attendees.")
    parser.set_defaults(need_notification=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = delete_event(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

