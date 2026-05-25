#!/usr/bin/env python3
"""
Shared read-only command layer for Feishu entrypoints.

This script formats index lookups for chat platforms. It deliberately keeps
write commands out; /remember and /forget need stronger confirmation rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def index_script(root: Path) -> Path:
    local = root / "scripts" / "codex-feishu-index.py"
    if local.exists():
        return local
    return Path(__file__).resolve().with_name("codex-feishu-index.py")


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|password|passwd|pwd)\s*[:=]\s*[\"']?[^\"'\s]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
]


def redact_text(text: str) -> str:
    value = str(text)
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def clean_display_text(text: str, limit: int = 180) -> str:
    value = redact_text(text)
    value = re.sub(r"<!--.*?-->", "", value)
    value = re.sub(r"^\ufeff", "", value)
    value = re.sub(r"^\s*-\s*\[[^\]]+\]\s*(\[[^\]]+\]\s*){0,3}", "", value)
    value = " ".join(value.split()).strip()
    if len(value) > limit:
        value = value[: max(0, limit - 3)] + "..."
    return value


def clean_error_text(text: str) -> str:
    return clean_display_text(text, 300)


def text_fingerprint(text: str) -> dict:
    raw = text.encode("utf-8", errors="replace")
    return {
        "len": len(text),
        "sha256_12": hashlib.sha256(raw).hexdigest()[:12],
    }


def append_run(root: Path, payload: dict) -> None:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("ts", int(time.time()))
    path = runs / f"{time.strftime('%Y-%m-%d', time.localtime())}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def infer_workspace(root: Path, cwd: Path | None = None) -> str | None:
    current = (cwd or Path.cwd()).resolve()
    try:
        current.relative_to(root)
    except ValueError:
        return None
    for candidate in [current, *current.parents]:
        manifest = candidate / "workspace_manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                workspace = str(data.get("workspace", "")).strip()
                return workspace or candidate.name
            except (OSError, json.JSONDecodeError):
                return candidate.name
        if candidate == root:
            break
    return None


def run_index(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    script = index_script(root)
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def parse_json_lines(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def format_results(title: str, rows: list[dict], workspace: str | None) -> str:
    if workspace:
        title = f"{title}（范围：{workspace}）"
    if not rows:
        return f"{title}\n没找到匹配结果。"
    lines = [title]
    for item in rows[:8]:
        path = item.get("path", "")
        name = item.get("title") or path
        summary = " ".join(str(item.get("summary", "")).split())
        if len(summary) > 120:
            summary = summary[:117] + "..."
        lines.append(f"- [{item.get('workspace', '')}/{item.get('kind', '')}] {name}")
        if path:
            lines.append(f"  {path}")
        if summary and summary != name:
            lines.append(f"  {summary}")
    return "\n".join(lines)[:1800]


def status(root: Path) -> tuple[int, str]:
    proc = run_index(root, ["status"])
    if proc.returncode != 0:
        return proc.returncode, f"索引状态失败：{proc.stderr.strip() or proc.stdout.strip()}"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    lines.extend(reindex_status_lines(root))
    return 0, "\n".join(["索引状态：", *lines])[:1800]


def reindex_status_lines(root: Path) -> list[str]:
    log = root / "memory" / "search" / "reindex.log"
    stamp = root / "memory" / "search" / "last-reindex.txt"
    lines = []
    if stamp.exists():
        lines.append(f"last_reindex={stamp.read_text(encoding='utf-8', errors='replace').strip()}")
    if not log.exists():
        lines.append("reindex_log=missing")
        return lines
    raw = [line.strip() for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not raw:
        lines.append("reindex_log=empty")
        return lines
    last_ok = next((line for line in reversed(raw) if " ok " in f" {line} "), "")
    last_skip = next((line for line in reversed(raw) if "skip " in line), "")
    last_fail = next((line for line in reversed(raw) if "failed " in line), "")
    if last_ok:
        lines.append(f"reindex_last_ok={last_ok}")
    if last_skip:
        lines.append(f"reindex_last_skip={last_skip}")
    if last_fail:
        lines.append(f"reindex_last_fail={last_fail}")
    return lines


def search(root: Path, workspace: str | None, query: str, title: str, kinds: list[str] | None = None) -> tuple[int, str, int]:
    if not query.strip():
        return 2, "用法：/files find 关键词 或 /memory search 关键词", 0
    args = ["search", query, "--limit", "8"]
    if workspace:
        args.extend(["--workspace", workspace])
    for kind in kinds or []:
        args.extend(["--kind", kind])
    proc = run_index(root, args)
    if proc.returncode != 0:
        return proc.returncode, f"索引查询失败：{proc.stderr.strip() or proc.stdout.strip()}", 0
    rows = parse_json_lines(proc.stdout)
    return 0, format_results(title, rows, workspace), len(rows)


def read_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def manifest_workspace(path: Path) -> str | None:
    manifest = path / "workspace_manifest.json"
    if not manifest.exists():
        return None
    data = read_manifest(manifest)
    workspace = str(data.get("workspace", "")).strip()
    return workspace or path.name


def workspace_base(root: Path, workspace: str | None) -> Path:
    root_workspace = manifest_workspace(root)
    if workspace is None or workspace in {".", root_workspace}:
        return root
    return root / workspace


def default_workspaces(root: Path) -> list[str]:
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


def selected_workspaces(root: Path, workspace: str | None) -> list[str]:
    if workspace:
        return [workspace]
    return default_workspaces(root)


def validate_workspace(root: Path, workspace: str | None) -> str | None:
    if workspace is None:
        return None
    value = str(workspace).strip()
    if not value:
        return None
    if value == ".":
        return value
    if Path(value).is_absolute() or "/" in value or "\\" in value or ".." in value:
        raise ValueError("workspace must be a manifest workspace name, not a path")
    if value == manifest_workspace(root):
        return value
    if not (root / value / "workspace_manifest.json").exists():
        raise ValueError(f"unknown workspace: {value}")
    return value


def selected_memory_scopes(root: Path, workspace: str | None) -> list[str]:
    if workspace:
        return [workspace]
    scopes = default_workspaces(root)
    if not scopes:
        scopes = ["."]
    return scopes


def recent_files(root: Path, workspace: str | None, limit_text: str) -> tuple[int, str, int]:
    try:
        limit = max(1, min(20, int(limit_text.strip() or "8")))
    except ValueError:
        limit = 8
    rows = []
    for name in selected_workspaces(root, workspace):
        local_files = workspace_base(root, name) / "local_files"
        if not local_files.exists():
            continue
        for path in local_files.rglob("*"):
            if not path.is_file() or path.name == "INDEX.md" or ".git" in path.parts:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append((stat.st_mtime, stat.st_size, name, path.relative_to(root).as_posix()))
    rows.sort(reverse=True)
    title = "最近文件："
    if workspace:
        title += f"（范围：{workspace}）"
    lines = [title]
    if not rows:
        lines.append("没有找到本地文件。")
        return 0, "\n".join(lines), 0
    for mtime, size, name, rel in rows[:limit]:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        lines.append(f"- [{name}] {rel} ({size} bytes, {ts})")
    return 0, "\n".join(lines)[:1800], min(len(rows), limit)


def pending_files(root: Path, workspace: str | None) -> tuple[int, str, int]:
    rows = []
    for name in selected_workspaces(root, workspace):
        incoming = workspace_base(root, name) / "local_files" / "incoming"
        if not incoming.exists():
            continue
        for path in incoming.rglob("*"):
            if path.is_file():
                rows.append((name, path.relative_to(root).as_posix()))
    title = "待分类文件："
    if workspace:
        title += f"（范围：{workspace}）"
    lines = [title]
    if not rows:
        lines.append("没有待分类 incoming 文件。")
        return 0, "\n".join(lines), 0
    for name, rel in rows[:20]:
        lines.append(f"- [{name}] {rel}")
    return 1, "\n".join(lines)[:1800], len(rows)


def knowledge_summary(root: Path, workspace: str | None) -> tuple[int, str, int]:
    rows = []
    for name in selected_workspaces(root, workspace):
        path = workspace_base(root, name) / "KNOWLEDGE.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        headings = [line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")]
        nonempty = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
        rows.append((name, path.relative_to(root).as_posix(), headings[:5], len(nonempty)))
    title = "知识库摘要："
    if workspace:
        title += f"（范围：{workspace}）"
    lines = [title]
    if not rows:
        lines.append("没有找到 KNOWLEDGE.md。")
        return 0, "\n".join(lines), 0
    for name, rel, headings, count in rows[:8]:
        head = " / ".join(headings) if headings else "无标题"
        lines.append(f"- [{name}] {rel} ({count} 条内容行)")
        lines.append(f"  {head[:160]}")
    return 0, "\n".join(lines)[:1800], len(rows)


def memory_base(root: Path, scope: str) -> Path:
    if scope == "." or workspace_base(root, scope) == root:
        return root / "memory"
    return root / scope / "memory"


def recent_memory(root: Path, workspace: str | None, limit_text: str) -> tuple[int, str, int]:
    try:
        limit = max(1, min(20, int(limit_text.strip() or "8")))
    except ValueError:
        limit = 8
    rows = []
    for scope in selected_memory_scopes(root, workspace):
        base = memory_base(root, scope)
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".jsonl"}:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            if path.suffix.lower() == ".jsonl":
                summary = "JSONL audit/event log"
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
                summary = next(
                    (
                        line.strip()
                        for line in reversed(text.splitlines())
                        if line.strip() and not line.lstrip().startswith("#")
                    ),
                    path.name,
                )
            rows.append((stat.st_mtime, scope, rel, summary[:180]))
    rows.sort(reverse=True)
    title = "最近记忆："
    if workspace:
        title += f"（范围：{workspace}）"
    lines = [title]
    if not rows:
        lines.append("没有找到记忆条目。")
        return 0, "\n".join(lines), 0
    for mtime, scope, rel, summary in rows[:limit]:
        label = "main" if scope == "." else scope
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        lines.append(f"- [{label}] {rel} ({ts})")
        lines.append(f"  {summary}")
    return 0, "\n".join(lines)[:1800], min(len(rows), limit)


def extract_heading_section(text: str, heading_name: str) -> list[str]:
    lines = text.splitlines()
    start = None
    level = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if heading_name in title:
            start = idx + 1
            level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start is None:
        return []
    section: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            current_level = len(stripped) - len(stripped.lstrip("#"))
            if current_level <= level:
                break
        if stripped:
            section.append(stripped)
    return section


def task_files(root: Path, scope: str) -> list[Path]:
    if scope == "." or workspace_base(root, scope) == root:
        base = root / "memory" / "tasks"
        return [path for path in (base / "open.md", base / "done.md") if path.exists()]
    base = root / scope / "memory"
    if not base.exists():
        return []
    return sorted(
        path
        for path in base.rglob("*.md")
        if "task" in path.name.lower() or "待办" in path.name or "shopping" in path.name.lower()
    )


def list_tasks(root: Path, workspace: str | None, limit_text: str) -> tuple[int, str, int]:
    try:
        limit = max(1, min(30, int(limit_text.strip() or "12")))
    except ValueError:
        limit = 12
    rows = []
    for scope in selected_memory_scopes(root, workspace):
        for path in task_files(root, scope):
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(root).as_posix()
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("---"):
                    continue
                if "status:done" in stripped and workspace:
                    continue
                rows.append((scope, rel, stripped[:180]))
        if scope != ".":
            knowledge = workspace_base(root, scope) / "KNOWLEDGE.md"
            if knowledge.exists():
                for line in extract_heading_section(knowledge.read_text(encoding="utf-8", errors="replace"), "待办"):
                    if line.startswith("- "):
                        rows.append((scope, knowledge.relative_to(root).as_posix(), line[:180]))
    title = "任务列表："
    if workspace:
        title += f"（范围：{workspace}）"
    lines = [title]
    if not rows:
        lines.append("没有找到任务条目。")
        return 0, "\n".join(lines), 0
    for scope, rel, item in rows[:limit]:
        label = "main" if scope == "." else scope
        lines.append(f"- [{label}] {item}")
        lines.append(f"  {rel}")
    return 0, "\n".join(lines)[:1800], min(len(rows), limit)


def workspace_info(root: Path, workspace: str | None) -> tuple[int, str, int]:
    scopes = selected_workspaces(root, workspace)
    lines = ["工作区信息：" + (f"（范围：{workspace}）" if workspace else "")]
    count = 0
    for scope in scopes[:6]:
        manifest = workspace_base(root, scope) / "workspace_manifest.json"
        if not manifest.exists():
            continue
        try:
            data = read_manifest(manifest)
        except (OSError, json.JSONDecodeError) as exc:
            lines.append(f"- [{scope}] manifest 读取失败：{type(exc).__name__}")
            continue
        count += 1
        entrypoints = data.get("entrypoints") or []
        commands = data.get("commands") or []
        sources = data.get("data_sources") or []
        lines.append(f"- [{scope}] {data.get('scope', '')}")
        lines.append(f"  root={data.get('root', '')}")
        lines.append(f"  entrypoints={len(entrypoints)} commands={len(commands)} data_sources={len(sources)}")
        if commands:
            lines.append("  " + " ".join(str(item) for item in commands[:12]))
    if count == 0:
        lines.append("没有找到 workspace_manifest.json。")
    return 0, "\n".join(lines)[:1800], count


def task_agent_script(root: Path) -> Path:
    local = root / "scripts" / "task-agent.py"
    if local.exists():
        return local
    return Path(__file__).resolve().with_name("task-agent.py")


def run_task_agent(root: Path, workspace: str | None, args: list[str]) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(task_agent_script(root)), "--root", str(root)]
    if workspace:
        argv.extend(["--workspace", workspace])
    argv.extend(args)
    return subprocess.run(
        argv,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def task_agent_list(root: Path, workspace: str | None) -> tuple[int, str, int]:
    proc = run_task_agent(root, workspace, ["--text", "list"])
    if proc.returncode != 0:
        return proc.returncode, f"任务代理查询失败：{clean_error_text(proc.stderr.strip() or proc.stdout.strip())}", 0
    count = sum(1 for line in proc.stdout.splitlines() if line.startswith("- "))
    return 0, proc.stdout.strip()[:1800], count


def task_agent_handle(root: Path, workspace: str | None, body: str, *, dry_run: bool) -> tuple[int, str, int]:
    if not body.strip():
        return 2, "用法：/task preview 自然语言任务 或 /task run 自然语言任务", 0
    task_args = ["--message", body]
    if dry_run:
        task_args.append("parse")
    else:
        if os.environ.get("CODEX_FEISHU_TASK_AGENT_CREATE_CALENDAR", "0") in {"1", "true", "TRUE", "yes", "YES"}:
            task_args.append("--create-calendar")
        task_args.append("handle")
    proc = run_task_agent(root, workspace, task_args)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode or 1, f"任务代理输出不可解析：{clean_error_text(proc.stderr.strip() or proc.stdout.strip())}", 0
    if not data.get("ok"):
        question = data.get("question")
        route = data.get("route") or {}
        result = data.get("result") or {}
        preview = result.get("preview")
        if question:
            return 1, f"任务代理：{question}", 0
        if preview:
            return 1, f"任务代理需要确认：{clean_display_text(preview, 500)}", 0
        if result.get("stage") == "calendar" or result.get("calendar"):
            calendar = result.get("calendar") or {}
            detail = calendar.get("result") or {}
            error_text = detail.get("stderr") or detail.get("stdout") or result.get("error") or data.get("error") or "未知错误"
            return 1, f"任务代理已写入本地任务，但飞书日程创建失败：{clean_error_text(str(error_text))[:700]}", 0
        task_type = route.get("task_type") or (data.get("spec") or {}).get("task_type") or "unknown"
        return 1, f"任务代理暂未执行：{task_type}，阶段 {data.get('stage') or result.get('stage') or 'unknown'}。", 0
    if dry_run:
        spec = data.get("spec") or {}
        validation = data.get("validation") or {}
        question = validation.get("question")
        if question:
            return 1, f"任务代理：{question}", 0
        return 0, f"任务代理预览：{spec.get('task_type')}\n{json.dumps(spec, ensure_ascii=False, indent=2)[:1500]}", 1
    spec = data.get("spec") or {}
    result = data.get("result") or {}
    task_type = spec.get("task_type")
    detail = result.get("preview") or result.get("path") or result.get("id") or "已完成"
    calendar = result.get("calendar") or {}
    if calendar.get("ok"):
        event = (calendar.get("result") or {}).get("data", {}).get("event", {})
        event_id = event.get("event_id") or (calendar.get("result") or {}).get("event_id")
        detail = f"{detail}\n飞书日程已创建" + (f"：{event_id}" if event_id else "")
    return 0, f"任务代理已执行：{task_type}\n{detail}", 1


def normalize_command(words: list[str]) -> tuple[str, str]:
    forbidden = {"--root", "--workspace"}
    for word in words:
        if word in forbidden or word.startswith("--root=") or word.startswith("--workspace="):
            return "forbidden-option", word
    if not words:
        return "help", ""
    head = words[0].lower()
    rest = " ".join(words[1:]).strip()
    if head in {"/status", "status", "状态"}:
        if rest.lower() in {"index", "索引", ""}:
            return "status-index", ""
    if head in {"/files", "files", "文件"}:
        parts = rest.split(maxsplit=1)
        if not parts:
            return "files-help", ""
        if parts[0].lower() in {"recent", "latest", "最近"}:
            return "files-recent", parts[1] if len(parts) > 1 else ""
        if parts[0].lower() in {"pending", "incoming", "待分类", "未分类"}:
            return "files-pending", ""
        if parts[0].lower() in {"find", "search", "找", "查"}:
            return "files-find", parts[1] if len(parts) > 1 else ""
        return "files-find", rest
    if head in {"/memory", "memory", "记忆", "/memfind", "memfind"}:
        parts = rest.split(maxsplit=1)
        if parts and parts[0].lower() in {"recent", "latest", "最近"}:
            return "memory-recent", parts[1] if len(parts) > 1 else ""
        if parts and parts[0].lower() in {"search", "find", "查", "找"}:
            return "memory-search", parts[1] if len(parts) > 1 else ""
        return "memory-search", rest
    if head in {"/knowledge", "knowledge", "知识库", "知识"}:
        parts = rest.split(maxsplit=1)
        if not parts or parts[0].lower() in {"summary", "概览", "摘要"}:
            return "knowledge-summary", parts[1] if len(parts) > 1 else ""
        if parts[0].lower() in {"search", "find", "查", "找"}:
            return "knowledge-search", parts[1] if len(parts) > 1 else ""
        return "knowledge-search", rest
    if head in {"/tasks", "tasks", "任务", "待办"}:
        parts = rest.split(maxsplit=1)
        if not parts or parts[0].lower() in {"list", "open", "ls", "列表", "查看"}:
            return "tasks-list", parts[1] if len(parts) > 1 else ""
        return "tasks-list", rest
    if head in {"/task", "task", "任务代理"}:
        parts = rest.split(maxsplit=1)
        if not parts or parts[0].lower() in {"list", "ls", "列表", "查看"}:
            return "task-agent-list", parts[1] if len(parts) > 1 else ""
        if parts[0].lower() in {"preview", "parse", "预览", "解析"}:
            return "task-agent-preview", parts[1] if len(parts) > 1 else ""
        if parts[0].lower() in {"run", "create", "执行", "创建"}:
            return "task-agent-run", parts[1] if len(parts) > 1 else ""
        return "task-agent-preview", rest
    if head in {"/workspace-info", "workspace-info", "/workspace", "workspace", "工作区"}:
        return "workspace-info", rest
    if head in {"/help", "help", "帮助"}:
        return "help", ""
    return "unknown", " ".join(words)


def help_text() -> str:
    return "\n".join(
        [
            "codex-feishu 只读命令：",
            "/status index：查看索引状态",
            "/files find 关键词：查文件、知识库、manifest",
            "/files recent：查看最近本地文件",
            "/files pending：查看待分类 incoming 文件",
            "/knowledge summary：查看当前工作区知识库摘要",
            "/knowledge search 关键词：查知识库",
            "/memfind 关键词：查记忆和项目记录",
            "/memfind recent：查看最近记忆条目",
            "/tasks list：查看当前工作区任务",
            "/task list：查看自然语言任务记录",
            "/task preview 自然语言任务：预览任务代理解析，不执行",
            "/task run 自然语言任务：执行低风险结构化任务；缺字段会先追问",
            "/workspace-info：查看当前工作区绑定与命令面",
            "查找类命令走 SQLite/FTS5；任务代理只执行低风险结构化写入，高风险文件/脚本/部署任务会停在确认。",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="codex-feishu shared bot command")
    parser.add_argument("--root", default=str(default_root()))
    parser.add_argument("--workspace", default=None)
    parser.add_argument("words", nargs="*")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    effective_workspace = validate_workspace(root, args.workspace or infer_workspace(root))
    started = time.time()
    cmd, body = normalize_command(args.words)
    code = 0
    result_count = None
    try:
        if cmd == "help" or cmd == "files-help":
            text = help_text()
        elif cmd == "status-index":
            code, text = status(root)
        elif cmd == "files-find":
            code, text, result_count = search(root, effective_workspace, body, "文件检索：")
        elif cmd == "files-recent":
            code, text, result_count = recent_files(root, effective_workspace, body)
        elif cmd == "files-pending":
            code, text, result_count = pending_files(root, effective_workspace)
        elif cmd == "memory-search":
            code, text, result_count = search(root, effective_workspace, body, "记忆检索：")
        elif cmd == "memory-recent":
            code, text, result_count = recent_memory(root, effective_workspace, body)
        elif cmd == "knowledge-summary":
            code, text, result_count = knowledge_summary(root, effective_workspace)
        elif cmd == "knowledge-search":
            code, text, result_count = search(root, effective_workspace, body, "知识库检索：", ["knowledge"])
        elif cmd == "tasks-list":
            code, text, result_count = list_tasks(root, effective_workspace, body)
        elif cmd == "task-agent-list":
            code, text, result_count = task_agent_list(root, effective_workspace)
        elif cmd == "task-agent-preview":
            code, text, result_count = task_agent_handle(root, effective_workspace, body, dry_run=True)
        elif cmd == "task-agent-run":
            code, text, result_count = task_agent_handle(root, effective_workspace, body, dry_run=False)
        elif cmd == "workspace-info":
            code, text, result_count = workspace_info(root, effective_workspace)
        elif cmd == "forbidden-option":
            code, text = 2, "命令参数里不能覆盖 --root 或 --workspace；请在当前工作区直接使用命令。"
        else:
            code, text = 2, help_text()
        print(text)
        append_run(
            root,
            {
                "tool": "codex-feishu-command",
                "cmd": cmd,
                "body": text_fingerprint(body),
                "workspace": effective_workspace,
                "workspace_source": "arg" if args.workspace else ("cwd" if effective_workspace else "global"),
                "ok": code == 0,
                "result_count": result_count,
                "duration_ms": int((time.time() - started) * 1000),
            },
        )
        return code
    except Exception as exc:
        append_run(
            root,
            {
                "tool": "codex-feishu-command",
                "cmd": cmd,
                "body": text_fingerprint(body),
                "workspace": effective_workspace,
                "workspace_source": "arg" if args.workspace else ("cwd" if effective_workspace else "global"),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": int((time.time() - started) * 1000),
            },
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
