#!/usr/bin/env python3
"""Check Feishu workspace local_files catalog health."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


LOCAL_DIRS = ["incoming", "docs", "data", "media", "code", "assets"]
PATH_RE = re.compile(r"`([^`]*local_files[\\/][^`]*)`")


def normalize(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/")


def extract_index_paths(index: Path) -> set[str]:
    text = index.read_text(encoding="utf-8", errors="replace")
    paths = set()
    for match in PATH_RE.finditer(text):
        value = normalize(match.group(1))
        if value.startswith("./"):
            value = value[2:]
        if value.startswith("../"):
            continue
        if "local_files/" in value:
            paths.add(value[value.index("local_files/") :])
    return paths


def is_covered(path: str, indexed: set[str]) -> bool:
    path = normalize(path)
    for item in indexed:
        item = normalize(item)
        if path == item:
            return True
        prefix = item if item.endswith("/") else item + "/"
        if path.startswith(prefix):
            return True
    return False


def top_level_assets(local_files: Path) -> Iterable[Path]:
    for dirname in ("docs", "data", "media", "code", "assets"):
        base = local_files / dirname
        if not base.exists():
            continue
        for item in sorted(base.iterdir(), key=lambda p: p.name):
            if item.name.startswith("."):
                continue
            yield item


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


def check_workspace(root: Path, workspace: str) -> dict:
    base = workspace_base(root, workspace)
    local_files = base / "local_files"
    failures: list[str] = []
    warnings: list[str] = []
    if not base.exists():
        return {"workspace": workspace, "ok": False, "failures": [f"missing workspace {base}"], "warnings": []}
    if not local_files.exists():
        return {
            "workspace": workspace,
            "ok": False,
            "failures": [f"missing local_files {local_files}"],
            "warnings": [],
        }
    for dirname in LOCAL_DIRS:
        if not (local_files / dirname).is_dir():
            failures.append(f"missing local_files/{dirname}/")
    index = local_files / "INDEX.md"
    if not index.exists():
        failures.append("missing local_files/INDEX.md")
        indexed: set[str] = set()
    else:
        indexed = extract_index_paths(index)
        if not indexed:
            warnings.append("local_files/INDEX.md has no indexed paths")
    for rel in sorted(indexed):
        target = base / rel
        if not target.exists():
            failures.append(f"INDEX references missing path: {rel}")
    incoming = local_files / "incoming"
    if incoming.exists():
        pending = [p.relative_to(base).as_posix() for p in incoming.rglob("*") if p.is_file()]
        for rel in sorted(pending):
            failures.append(f"unclassified incoming file: {rel}")
    uncovered = []
    for item in top_level_assets(local_files):
        rel = item.relative_to(base).as_posix()
        if not is_covered(rel, indexed):
            uncovered.append(rel + ("/" if item.is_dir() else ""))
    for rel in uncovered:
        failures.append(f"top-level local file not in INDEX: {rel}")
    return {
        "workspace": workspace,
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "indexed_paths": len(indexed),
        "top_level_assets": sum(1 for _ in top_level_assets(local_files)),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check codex-feishu local_files catalog health")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--workspace", action="append", dest="workspaces")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    workspaces = args.workspaces or discover_workspaces(root)
    if not workspaces:
        workspaces = ["."]
    results = [check_workspace(root, workspace) for workspace in workspaces]
    ok = all(item["ok"] for item in results)
    if args.json:
        print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False))
    else:
        for item in results:
            status = "ok" if item["ok"] else "fail"
            print(
                f"{item['workspace']}={status} indexed_paths={item.get('indexed_paths', 0)} "
                f"top_level_assets={item.get('top_level_assets', 0)}"
            )
            for warning in item.get("warnings", []):
                print(f"warning.{item['workspace']}={warning}")
            for failure in item.get("failures", []):
                print(f"failure.{item['workspace']}={failure}")
        print(f"file_health={'ok' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
