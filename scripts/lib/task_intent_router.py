#!/usr/bin/env python3
"""Lightweight natural-language task classifier for codex-feishu Feishu bots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
from pathlib import Path
from typing import Any


FIXED_COMMANDS = {
    "/files",
    "/memfind",
    "/memory",
    "/knowledge",
    "/tasks",
    "/task",
    "/workspace-info",
    "/workspace",
    "/status",
    "/status-index",
    "/health-codex-feishu",
    "/help",
    "/画图",
    "/生图",
    "/img",
}

PROJECT_WORKSPACES: dict[str, str] = {}


@dataclass
class TaskRoute:
    kind: str
    task_type: str | None
    confidence: float
    route: str
    target_layer: str | None
    workspace: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(float(self.confidence), 2)
        return data


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def starts_with_fixed_command(text: str) -> bool:
    stripped = normalize_text(text)
    if not stripped.startswith("/"):
        return False
    head = stripped.split(maxsplit=1)[0].lower()
    return head in FIXED_COMMANDS


def infer_workspace(root: Path | None = None, cwd: Path | None = None, project: str | None = None) -> str | None:
    project_map = dict(PROJECT_WORKSPACES)
    try:
        raw_map = os.environ.get("CODEX_FEISHU_PROJECT_WORKSPACE_MAP", "")
        data = json.loads(raw_map) if raw_map else {}
        if isinstance(data, dict):
            project_map.update({str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()})
    except json.JSONDecodeError:
        pass
    if project and project in project_map:
        return project_map[project]
    env_workspace = os.environ.get("CODEX_FEISHU_WORKSPACE_NAME", "").strip()
    if env_workspace:
        return env_workspace
    root = (root or Path(os.environ.get("CODEX_FEISHU_ROOT", "/opt/codex-feishu"))).resolve()
    current = (cwd or Path.cwd()).resolve()
    try:
        current.relative_to(root)
    except ValueError:
        return None
    for candidate in [current, *current.parents]:
        if candidate == root:
            break
        manifest = candidate / "workspace_manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                workspace = str(data.get("workspace") or "").strip()
                return workspace or candidate.name
            except Exception:
                return candidate.name
    return "private"


def classify_task_intent(
    message: str,
    *,
    workspace: str | None = None,
    project: str | None = None,
    root: Path | None = None,
    cwd: Path | None = None,
) -> TaskRoute:
    text = normalize_text(message)
    scope = workspace or infer_workspace(root=root, cwd=cwd, project=project)
    if not text:
        return TaskRoute("chat", None, 0.0, "ignore", None, scope, "empty")
    if starts_with_fixed_command(text):
        return TaskRoute("command", None, 1.0, "deterministic_command", None, scope, "fixed_command")

    lowered = text.lower()
    rota_terms = ("值日", "轮值", "排班", "轮休", "本周", "顺序")
    reminder_terms = ("提醒", "日程", "闹钟", "每天", "每周", "明天", "后天")
    file_terms = ("文件", "脚本", "py", ".py", "上传", "发回来", "改好", "修改")
    deploy_terms = ("部署", "重启", "restart", "systemctl", "上线", "更新服务", "bot 服务", "bot服务")
    script_terms = ("写个脚本", "创建脚本", "生成脚本", "跑一下", "运行脚本")
    memory_terms = ("记住", "帮我记", "记录一下", "以后记得")
    calendar_delete_terms = ("删除", "取消", "删掉", "撤销", "delete", "cancel")

    def has_any(terms: tuple[str, ...]) -> bool:
        return any(term in lowered or term in text for term in terms)

    if has_any(rota_terms) and has_any(reminder_terms):
        return TaskRoute("task", "weekly_rota", 0.88, "model_parse_then_script_execute", "mention-fast", scope, "rota_keywords")
    if has_any(calendar_delete_terms) and ("event_id" in lowered or "日程" in text or "提醒" in text or "轮值" in text):
        return TaskRoute("task", "calendar_event_delete", 0.82, "preview_confirm_then_execute", "mention-fast", scope, "calendar_delete_keywords")
    if has_any(file_terms) and any(term in text for term in ("改", "限制", "只读", "发回来", "处理", "转换")):
        return TaskRoute("task", "file_modify_and_return", 0.82, "model_parse_then_script_execute", "deep", scope, "file_modify_keywords")
    if has_any(deploy_terms):
        return TaskRoute("task", "deploy_or_restart", 0.78, "confirm_then_execute", "deep", scope, "deploy_keywords")
    if has_any(script_terms):
        return TaskRoute("task", "script_create_and_run", 0.74, "model_parse_then_script_execute", "deep", scope, "script_keywords")
    if has_any(memory_terms):
        return TaskRoute("task", "memory_write", 0.78, "script_execute", "mention-fast", scope, "memory_keywords")
    if "提醒" in text and (has_any(reminder_terms) or re.search(r"\d{1,2}[:点]", text)):
        return TaskRoute("task", "scheduled_reminder", 0.86, "model_parse_then_script_execute", "mention-fast", scope, "reminder_keywords")
    if any(term in text for term in ("帮我", "帮忙", "请你")) and any(term in text for term in ("做", "创建", "改", "整理", "检查")):
        return TaskRoute("task", "script_create_and_run", 0.61, "model_parse_then_script_execute", "deep", scope, "generic_action_request")
    return TaskRoute("chat", None, 0.25, "normal_chat", None, scope, "no_task_signal")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Classify codex-feishu natural-language task intent.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--project", default=os.environ.get("CC_HOOK_PROJECT", ""))
    parser.add_argument("--root", default=os.environ.get("CODEX_FEISHU_ROOT", str(Path(__file__).resolve().parents[2])))
    args = parser.parse_args()
    route = classify_task_intent(args.message, workspace=args.workspace, project=args.project, root=Path(args.root))
    print(json.dumps(route.to_dict(), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

