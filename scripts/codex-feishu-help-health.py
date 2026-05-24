#!/usr/bin/env python3
"""Check static /help guides include the current Feishu command surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


REQUIRED_SNIPPETS = [
    "/health-codex-feishu",
    "/workspace-info",
    "/files find",
    "/files recent",
    "/files pending",
    "/knowledge summary",
    "/knowledge search",
    "/memfind",
    "/memfind recent",
    "/tasks list",
]


def manifest_workspace(path: Path) -> str | None:
    manifest = path / "workspace_manifest.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return path.name
    workspace = str(data.get("workspace", "")).strip()
    return workspace or path.name


def workspace_base(root: Path, workspace: str) -> Path:
    root_workspace = manifest_workspace(root)
    if workspace in {".", root_workspace}:
        return root
    return root / workspace


def discover_workspaces(root: Path) -> list[str]:
    names: list[str] = []
    root_workspace = manifest_workspace(root)
    if root_workspace:
        names.append(root_workspace)
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if not item.is_dir() or item.name.startswith(".") or item.name in {"memory", "runs", "scripts", "docs", "templates"}:
            continue
        name = manifest_workspace(item)
        if name and name not in names:
            names.append(name)
    return names


def check_help(root: Path, workspace: str) -> dict:
    base = workspace_base(root, workspace)
    path = base / "local_files" / "docs" / "help-guide.md"
    failures: list[str] = []
    if not path.exists():
        return {"workspace": workspace, "ok": False, "failures": [f"missing {path}"]}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in text:
            failures.append(f"missing help snippet {snippet}")
    if "Group bots only use this generated workspace" not in text and "只使用这个生成工作区" not in text:
        failures.append("missing workspace boundary statement")
    return {"workspace": workspace, "ok": not failures, "failures": failures, "path": path.relative_to(root).as_posix()}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check codex-feishu static help guides")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    results = [check_help(root, workspace) for workspace in discover_workspaces(root)]
    if not results:
        results = [check_help(root, ".")]
    ok = all(item["ok"] for item in results)
    if args.json:
        print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False))
    else:
        for item in results:
            status = "ok" if item["ok"] else "fail"
            print(f"help.{item['workspace']}={status} path={item.get('path', '')}")
            for failure in item.get("failures", []):
                print(f"failure.{item['workspace']}={failure}")
        print(f"help_health={'ok' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
