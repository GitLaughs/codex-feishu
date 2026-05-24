#!/usr/bin/env python3
"""Check codex-feishu Feishu memory store health."""

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


MAIN_DIRS = ["daily", "facts", "inbox", "people", "projects", "reviews", "search", "tasks"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"),
]


def iter_memory_files(memory: Path) -> Iterable[Path]:
    if not memory.exists():
        return
    for path in memory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".jsonl", ".txt"}:
            continue
        yield path


def check_json(path: Path, failures: list[str]) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
    except Exception as exc:
        failures.append(f"invalid json: {path}: {type(exc).__name__}: {exc}")


def check_jsonl(path: Path, failures: list[str]) -> None:
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except Exception as exc:
            failures.append(f"invalid jsonl: {path}:{lineno}: {type(exc).__name__}: {exc}")
            if len(failures) > 50:
                return


def check_secret_patterns(path: Path, failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            failures.append(f"possible secret pattern in memory file: {path}")
            return


def check_main_memory(root: Path) -> dict:
    memory = root / "memory"
    failures: list[str] = []
    warnings: list[str] = []
    if not memory.exists():
        return {"scope": "main", "ok": False, "failures": [f"missing {memory}"], "warnings": []}
    for dirname in MAIN_DIRS:
        if not (memory / dirname).is_dir():
            failures.append(f"missing memory/{dirname}/")
    explicit_json = {"triggers.json", "heartbeat-state.json"}
    for name in explicit_json:
        path = memory / name
        if path.exists():
            check_json(path, failures)
        elif name == "triggers.json":
            failures.append("missing memory/triggers.json")
    daily = sorted((memory / "daily").glob("*.md")) if (memory / "daily").exists() else []
    if not daily:
        warnings.append("memory/daily has no daily markdown files")
    for path in iter_memory_files(memory):
        rel = path.relative_to(memory).as_posix()
        if rel in explicit_json:
            check_secret_patterns(path, failures)
            continue
        if path.suffix.lower() == ".json":
            check_json(path, failures)
        elif path.suffix.lower() == ".jsonl":
            check_jsonl(path, failures)
        check_secret_patterns(path, failures)
    return {
        "scope": "main",
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "files": sum(1 for _ in iter_memory_files(memory)),
        "daily_files": len(daily),
    }


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


def check_workspace_memory(root: Path, workspace: str) -> dict:
    base = workspace_base(root, workspace)
    memory = base / "memory"
    failures: list[str] = []
    warnings: list[str] = []
    if not base.exists():
        return {"scope": workspace, "ok": False, "failures": [f"missing workspace {base}"], "warnings": []}
    if (base / "MEMORY.md").exists():
        failures.append(f"{workspace}/MEMORY.md must not exist in group workspace")
    if not memory.exists():
        warnings.append(f"{workspace}/memory missing")
        files = 0
    else:
        files = 0
        for path in iter_memory_files(memory):
            files += 1
            if path.suffix.lower() == ".json":
                check_json(path, failures)
            elif path.suffix.lower() == ".jsonl":
                check_jsonl(path, failures)
            check_secret_patterns(path, failures)
    return {"scope": workspace, "ok": not failures, "failures": failures, "warnings": warnings, "files": files}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check codex-feishu memory health")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if manifest_workspace(root):
        results = [check_workspace_memory(root, manifest_workspace(root) or ".")]
    else:
        results = [check_main_memory(root)]
        results.extend(check_workspace_memory(root, workspace) for workspace in discover_workspaces(root))
    ok = all(item["ok"] for item in results)
    if args.json:
        print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False))
    else:
        for item in results:
            status = "ok" if item["ok"] else "fail"
            print(f"memory.{item['scope']}={status} files={item.get('files', 0)} daily_files={item.get('daily_files', '-')}")
            for warning in item.get("warnings", []):
                print(f"warning.{item['scope']}={warning}")
            for failure in item.get("failures", []):
                print(f"failure.{item['scope']}={failure}")
        print(f"memory_health={'ok' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
