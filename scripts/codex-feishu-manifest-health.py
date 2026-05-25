#!/usr/bin/env python3
"""Validate codex-feishu Feishu workspace manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


REQUIRED_COMMANDS = [
    "/help",
    "/status-index",
    "/health-codex-feishu",
    "/files",
    "/files find",
    "/files recent",
    "/files pending",
    "/knowledge",
    "/knowledge summary",
    "/knowledge search",
    "/memfind",
    "/memfind recent",
    "/tasks",
    "/tasks list",
    "/task",
    "/task list",
    "/task preview",
    "/task run",
    "/workspace-info",
]
PLANNED_ONLY_PREFIXES = ["/remember", "/forget", "/memory review", "/files describe", "/files ingest", "/files link", "/files archive"]
REQUIRED_SOURCES = ["INSTRUCTIONS.md", "KNOWLEDGE.md", "memory/", "local_files/", "workspace_manifest.json"]


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


def check_manifest(root: Path, workspace: str) -> dict:
    base = workspace_base(root, workspace)
    path = base / "workspace_manifest.json"
    failures: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return {"workspace": workspace, "ok": False, "failures": [f"missing {path}"], "warnings": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "workspace": workspace,
            "ok": False,
            "failures": [f"invalid json: {type(exc).__name__}: {exc}"],
            "warnings": [],
        }
    if data.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    if data.get("workspace") != workspace:
        failures.append(f"workspace field mismatch: {data.get('workspace')!r}")
    if "cloud_root" in data and not str(data.get("cloud_root", "")).strip():
        failures.append("cloud_root must not be empty when present")
    commands = set(data.get("commands") or [])
    for command in REQUIRED_COMMANDS:
        if command not in commands:
            failures.append(f"missing command {command}")
    planned = set(data.get("planned_commands") or [])
    overlap = commands & planned
    for command in sorted(overlap):
        failures.append(f"command appears in both commands and planned_commands: {command}")
    for command in sorted(commands):
        if any(command == prefix or command.startswith(prefix + " ") for prefix in PLANNED_ONLY_PREFIXES):
            failures.append(f"planned write command must not be active yet: {command}")
    for command in sorted(planned):
        if not any(command == prefix or command.startswith(prefix + " ") for prefix in PLANNED_ONLY_PREFIXES):
            warnings.append(f"planned command has no recognized roadmap prefix: {command}")
    sources = set(data.get("data_sources") or [])
    for source in REQUIRED_SOURCES:
        if source not in sources:
            failures.append(f"missing data_source {source}")
        else:
            target = base / source.rstrip("/")
            if not target.exists():
                failures.append(f"data_source does not exist: {source}")
    entrypoints = data.get("entrypoints") or []
    if not entrypoints:
        failures.append("entrypoints must not be empty")
    elif not all(item.get("platform") == "feishu" for item in entrypoints if isinstance(item, dict)):
        failures.append("all entrypoints must be Feishu")
    guardrails = data.get("guardrails") or []
    if len(guardrails) < 2:
        warnings.append("guardrails has fewer than 2 entries")
    policy = data.get("resource_policy") or {}
    if policy.get("preferred_storage") != "sqlite_fts5":
        failures.append("resource_policy.preferred_storage must be sqlite_fts5")
    avoid = set(policy.get("avoid") or [])
    if not any("vector" in item for item in avoid):
        warnings.append("resource_policy.avoid should mention vector service avoidance")
    return {
        "workspace": workspace,
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "commands": len(commands),
        "planned_commands": len(planned),
        "entrypoints": len(entrypoints),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check codex-feishu workspace manifests")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    results = [check_manifest(root, workspace) for workspace in discover_workspaces(root)]
    if not results:
        results = [check_manifest(root, ".")]
    ok = all(item["ok"] for item in results)
    if args.json:
        print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False))
    else:
        for item in results:
            status = "ok" if item["ok"] else "fail"
            print(
                f"manifest.{item['workspace']}={status} "
                f"commands={item.get('commands', 0)} planned_commands={item.get('planned_commands', 0)} "
                f"entrypoints={item.get('entrypoints', 0)}"
            )
            for warning in item.get("warnings", []):
                print(f"warning.{item['workspace']}={warning}")
            for failure in item.get("failures", []):
                print(f"failure.{item['workspace']}={failure}")
        print(f"manifest_health={'ok' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
