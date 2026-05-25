#!/usr/bin/env python3
"""codex-feishu natural-language task agent core.

This script turns chat text into structured task specs, validates them, and
executes low-risk deterministic pieces inside the current codex-feishu workspace.
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
import tempfile
import time
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.task_intent_router import classify_task_intent  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DAY_NAMES = {
    "日": 0,
    "天": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
}

TASK_TYPES = {
    "weekly_rota",
    "scheduled_reminder",
    "calendar_event_delete",
    "file_modify_and_return",
    "script_create_and_run",
    "deploy_or_restart",
    "memory_write",
}


def stable_id(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def workspace_root(root: Path, workspace: str | None) -> Path:
    if not workspace or workspace in {".", "private"}:
        return root
    if Path(workspace).is_absolute() or "/" in workspace or "\\" in workspace or ".." in workspace:
        raise ValueError("workspace must be a workspace name, not a path")
    candidate = (root / workspace).resolve()
    candidate.relative_to(root.resolve())
    if not (candidate / "workspace_manifest.json").exists():
        raise ValueError(f"unknown workspace: {workspace}")
    return candidate


def workspace_manifest(root: Path, workspace: str | None) -> dict[str, Any]:
    base = workspace_root(root, workspace)
    manifest = base / "workspace_manifest.json"
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def workspace_chat_id(root: Path, workspace: str | None) -> str:
    data = workspace_manifest(root, workspace)
    feishu = data.get("feishu") if isinstance(data.get("feishu"), dict) else {}
    return str(feishu.get("chat_id") or data.get("chat_id") or "").strip()


def feishu_actions_for_spec(root: Path, spec: dict[str, Any]) -> list[dict[str, Any]]:
    task_type = spec.get("task_type")
    actions: list[dict[str, Any]] = []
    if task_type in {"weekly_rota", "scheduled_reminder"} and (spec.get("notify") or {}).get("create_feishu_calendar"):
        actions.append(
            {
                "service": "calendar",
                "action": "create_event",
                "via": "lark-cli calendar events create",
                "identity": "user",
                "recurrence": "weekly" if task_type == "weekly_rota" else (spec.get("schedule") or {}).get("type"),
            }
        )
    if task_type == "calendar_event_delete":
        actions.append(
            {
                "service": "calendar",
                "action": "delete_event",
                "via": "delete-feishu-reminder.py",
                "identity": "user",
                "requires_confirmation": True,
            }
        )
    if task_type == "weekly_rota" and (spec.get("notify") or {}).get("mention_assignees"):
        actions.append({"service": "im", "action": "send_group_message_with_mentions", "via": "cc-connect reply"})
    if task_type == "file_modify_and_return":
        actions.append({"service": "drive", "action": "upload_modified_file", "via": "lark-cli drive upload"})
    if task_type == "deploy_or_restart":
        actions.append({"service": "systemd", "action": "restart_cc_connect", "requires_confirmation": True})
    chat_id = workspace_chat_id(root, spec.get("workspace"))
    if chat_id and any(item.get("service") == "calendar" for item in actions):
        for item in actions:
            if item.get("service") == "calendar":
                item["attendee_ids"] = [chat_id]
    return actions


def parse_day_of_week(text: str) -> int | None:
    match = re.search(r"(?:每周|周|星期|礼拜)([日天一二三四五六])", text)
    if match:
        return DAY_NAMES.get(match.group(1))
    return None


def parse_time_of_day(text: str) -> str | None:
    match = re.search(r"(?:(上午|早上|下午|晚上|夜里|中午)\s*)?(\d{1,2})(?::|：)(\d{2})", text)
    if not match:
        match = re.search(r"(?:(上午|早上|下午|晚上|夜里|中午)\s*)?(\d{1,2})\s*点\s*(半|[0-5]?\d分?)?", text)
    if not match:
        return None
    period = match.group(1) or ""
    hour = int(match.group(2))
    if match.lastindex and match.lastindex >= 3:
        minute_text = match.group(3) or "0"
    else:
        minute_text = "0"
    if minute_text == "半":
        minute = 30
    else:
        minute_digits = re.sub(r"\D", "", minute_text)
        minute = int(minute_digits or "0")
    if period in {"下午", "晚上", "夜里"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def split_items(text: str) -> list[str]:
    return [item.strip(" ，,;；、。") for item in re.split(r"[、,，;；]", text) if item.strip(" ，,;；、。")]


def parse_rota_tasks(text: str) -> list[str]:
    match = re.search(r"(?:整体)?值日顺序[:：]\s*([^。\n]+)", text)
    if not match:
        match = re.search(r"(?:轮值|轮换|顺序)[:：]\s*([^。\n]+)", text)
    if not match:
        return []
    return split_items(match.group(1))


def parse_rota_assignments(text: str, tasks: list[str]) -> dict[str, str]:
    match = re.search(r"本周[:：]\s*([^。\n]+)", text)
    if not match:
        return {}
    raw = match.group(1)
    assignments: dict[str, str] = {}
    chunks = split_items(raw)
    known_tasks = sorted(tasks, key=len, reverse=True)
    for chunk in chunks:
        for task in known_tasks:
            if task and task in chunk:
                name = chunk.replace(task, " ").strip()
                name = re.sub(r"\s+", " ", name).strip()
                if name:
                    assignments[name] = task
                break
    return assignments


def title_from_message(text: str, fallback: str) -> str:
    value = re.sub(r"\s+", " ", text).strip(" ，,。")
    if len(value) <= 24:
        return value or fallback
    return fallback


def parse_weekly_rota(text: str, workspace: str | None, root: Path | None = None) -> dict[str, Any]:
    tasks = parse_rota_tasks(text)
    assignments = parse_rota_assignments(text, tasks)
    spec = {
        "task_type": "weekly_rota",
        "title": "值日提醒",
        "day_of_week": parse_day_of_week(text),
        "time": parse_time_of_day(text),
        "timezone": "Asia/Shanghai",
        "tasks": tasks or None,
        "current_assignments": assignments or None,
        "rotation": {"direction": "next_task", "shift_per_run": 1},
        "notify": {"mention_assignees": True, "create_feishu_calendar": True},
        "workspace": workspace,
    }
    if root is not None:
        chat_id = workspace_chat_id(root, workspace)
        if chat_id:
            spec["attendee_ids"] = [chat_id]
        spec["feishu_actions"] = feishu_actions_for_spec(root, spec)
    return spec


def parse_scheduled_reminder(text: str, workspace: str | None, root: Path | None = None) -> dict[str, Any]:
    schedule_type = "daily" if any(term in text for term in ("每天", "每日")) else "weekly" if "每周" in text else "once"
    message = text
    match = re.search(r"提醒我(.+)", text)
    if match:
        message = match.group(1).strip(" ，,。")
    spec = {
        "task_type": "scheduled_reminder",
        "title": title_from_message(message, "提醒"),
        "schedule": {
            "type": schedule_type,
            "day_of_week": parse_day_of_week(text) if schedule_type == "weekly" else None,
            "time": parse_time_of_day(text),
            "timezone": "Asia/Shanghai",
        },
        "message": message,
        "notify": {"mention_user": None, "create_feishu_calendar": True},
        "workspace": workspace,
    }
    if root is not None:
        chat_id = workspace_chat_id(root, workspace)
        if chat_id:
            spec["attendee_ids"] = [chat_id]
        spec["feishu_actions"] = feishu_actions_for_spec(root, spec)
    return spec


def parse_calendar_event_delete(text: str, workspace: str | None, root: Path | None = None) -> dict[str, Any]:
    match = re.search(r"(?:event_id\s*[=:：]?\s*)?([A-Za-z0-9][A-Za-z0-9_.:-]{7,255})", text)
    event_id = match.group(1) if match else None
    spec = {
        "task_type": "calendar_event_delete",
        "event_id": event_id,
        "workspace": workspace,
        "requires_confirmation": True,
    }
    if root is not None:
        spec["feishu_actions"] = feishu_actions_for_spec(root, spec)
    return spec


def parse_file_modify(text: str, workspace: str | None, source_file: str | None = None) -> dict[str, Any]:
    source = source_file
    if not source:
        match = re.search(r"([\w./\\\-\u4e00-\u9fff]+?\.(?:py|md|txt|json|csv|docx|xlsx))", text, re.I)
        if match:
            source = match.group(1).replace("\\", "/")
    output = None
    if source:
        path = Path(source)
        output = str(path.with_name(f"{path.stem}-modified{path.suffix}")).replace("\\", "/")
    return {
        "task_type": "file_modify_and_return",
        "source_file": source,
        "instructions": text,
        "output_path": output,
        "checks": ["syntax"] if (source or "").lower().endswith(".py") else [],
        "upload_to_chat": True,
        "workspace": workspace,
    }


def parse_script_create(text: str, workspace: str | None) -> dict[str, Any]:
    return {
        "task_type": "script_create_and_run",
        "title": title_from_message(text, "创建脚本"),
        "description": text,
        "language": "python" if "py" in text.lower() or "python" in text.lower() else None,
        "output_path": None,
        "run_after_create": False,
        "checks": ["syntax"],
        "workspace": workspace,
    }


def parse_deploy(text: str, workspace: str | None) -> dict[str, Any]:
    action = "restart" if any(term in text.lower() for term in ("重启", "restart")) else "deploy"
    target = "cc-connect"
    return {
        "task_type": "deploy_or_restart",
        "action": action,
        "target": target,
        "reason": text,
        "requires_confirmation": True,
        "health_check": "codex-feishu-healthcheck.sh",
        "workspace": workspace,
    }


def parse_memory_write(text: str, workspace: str | None) -> dict[str, Any]:
    content = re.sub(r"^(记住|帮我记住|记录一下)[:：，, ]*", "", text).strip()
    return {
        "task_type": "memory_write",
        "action": "create",
        "target": "facts",
        "content": content or None,
        "tags": ["user"],
        "workspace": workspace,
    }


def parse_task_spec(
    message: str,
    task_type: str,
    workspace: str | None = None,
    source_file: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    root = root or ROOT
    if task_type == "weekly_rota":
        return parse_weekly_rota(message, workspace, root)
    if task_type == "scheduled_reminder":
        return parse_scheduled_reminder(message, workspace, root)
    if task_type == "calendar_event_delete":
        return parse_calendar_event_delete(message, workspace, root)
    if task_type == "file_modify_and_return":
        return parse_file_modify(message, workspace, source_file=source_file)
    if task_type == "script_create_and_run":
        return parse_script_create(message, workspace)
    if task_type == "deploy_or_restart":
        return parse_deploy(message, workspace)
    if task_type == "memory_write":
        return parse_memory_write(message, workspace)
    raise ValueError(f"unsupported task_type: {task_type}")


def missing_question(task_type: str, field: str) -> str:
    questions = {
        ("weekly_rota", "day_of_week"): "还缺提醒星期：每周几提醒？",
        ("weekly_rota", "time"): "还缺提醒时间：几点提醒？",
        ("weekly_rota", "tasks"): "还缺轮值顺序：有哪些值日项？",
        ("weekly_rota", "current_assignments"): "还缺本周分配：谁负责哪一项？",
        ("scheduled_reminder", "schedule.time"): "还缺提醒时间：几点提醒？",
        ("scheduled_reminder", "message"): "还缺提醒内容：要提醒什么？",
        ("calendar_event_delete", "event_id"): "还缺要取消的日程 event_id。",
        ("file_modify_and_return", "source_file"): "还缺要修改的文件：请上传文件或给出 local_files 路径。",
        ("file_modify_and_return", "instructions"): "还缺修改要求：要怎么改？",
        ("script_create_and_run", "language"): "还缺脚本语言：用 Python 还是其他语言？",
        ("script_create_and_run", "output_path"): "还缺保存路径：脚本保存到哪里？",
        ("memory_write", "content"): "还缺要记住的内容。",
    }
    return questions.get((task_type, field), f"还缺字段：{field}")


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    task_type = spec.get("task_type")
    missing: list[str] = []
    errors: list[str] = []
    if task_type not in TASK_TYPES:
        errors.append("task_type")
        return {"ok": False, "missing_fields": missing, "errors": errors, "question": "任务类型不支持。"}

    if task_type == "weekly_rota":
        for field in ("day_of_week", "time", "tasks", "current_assignments"):
            if spec.get(field) in (None, "", [], {}):
                missing.append(field)
        if spec.get("day_of_week") is not None and spec.get("day_of_week") not in range(7):
            errors.append("day_of_week")
        if spec.get("time") and not re.fullmatch(r"\d{2}:\d{2}", str(spec.get("time"))):
            errors.append("time")
    elif task_type == "scheduled_reminder":
        schedule = spec.get("schedule") if isinstance(spec.get("schedule"), dict) else {}
        if not schedule.get("time"):
            missing.append("schedule.time")
        if not spec.get("message"):
            missing.append("message")
        if schedule.get("time") and not re.fullmatch(r"\d{2}:\d{2}", str(schedule.get("time"))):
            errors.append("schedule.time")
    elif task_type == "calendar_event_delete":
        event_id = str(spec.get("event_id") or "")
        if not event_id:
            missing.append("event_id")
        elif not re.fullmatch(r"[A-Za-z0-9_.:-]{8,256}", event_id):
            errors.append("event_id")
        if not spec.get("requires_confirmation"):
            errors.append("requires_confirmation must be true")
    elif task_type == "file_modify_and_return":
        for field in ("source_file", "instructions"):
            if not spec.get(field):
                missing.append(field)
        source = str(spec.get("source_file") or "")
        output = str(spec.get("output_path") or "")
        if source and not source.startswith("local_files/"):
            errors.append("source_file must be under local_files/")
        if output and not output.startswith("local_files/"):
            errors.append("output_path must be under local_files/")
    elif task_type == "script_create_and_run":
        for field in ("language", "output_path"):
            if not spec.get(field):
                missing.append(field)
    elif task_type == "deploy_or_restart":
        if not spec.get("requires_confirmation"):
            errors.append("requires_confirmation must be true")
    elif task_type == "memory_write":
        if not spec.get("content"):
            missing.append("content")

    return {
        "ok": not missing and not errors,
        "missing_fields": missing,
        "errors": errors,
        "question": missing_question(str(task_type), missing[0]) if missing else "",
    }


def rota_preview(spec: dict[str, Any]) -> str:
    tasks = list(spec.get("tasks") or [])
    assignments = dict(spec.get("current_assignments") or {})
    current = []
    next_week = []
    for person, task in assignments.items():
        current.append(f"{task}->{person}")
        if task in tasks:
            next_task = tasks[(tasks.index(task) + int((spec.get("rotation") or {}).get("shift_per_run", 1))) % len(tasks)]
            next_week.append(f"{next_task}->{person}")
    return f"本周：{'，'.join(current)}；下周：{'，'.join(next_week)}"


def create_rota_from_spec(root: Path, spec: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    base = workspace_root(root, spec.get("workspace"))
    store = base / "memory" / "rotas.json"
    data = load_json(store, {"rotas": []})
    rotas = data.setdefault("rotas", [])
    key = {
        "day_of_week": spec.get("day_of_week"),
        "time": spec.get("time"),
        "tasks": spec.get("tasks"),
    }
    for item in rotas:
        if item.get("status", "active") == "active" and {k: item.get(k) for k in key} == key:
            return {"ok": False, "duplicate": True, "id": item.get("id"), "preview": rota_preview(item)}
    record = dict(spec)
    record.update(
        {
            "id": stable_id("rota", key | {"assignments": spec.get("current_assignments")}),
            "status": "active",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "preview": rota_preview(spec),
        }
    )
    if not dry_run:
        rotas.append(record)
        save_json(store, data)
    return {"ok": True, "id": record["id"], "path": str(store), "dry_run": dry_run, "preview": record["preview"]}


def create_rota_with_calendar(root: Path, spec: dict[str, Any], *, dry_run: bool = False, create_calendar: bool = False) -> dict[str, Any]:
    result = create_rota_from_spec(root, spec, dry_run=dry_run)
    if result.get("ok") and create_calendar and (spec.get("notify") or {}).get("create_feishu_calendar"):
        calendar_spec = scheduled_spec_from_rota(root, spec)
        calendar = call_calendar(root, calendar_spec, dry_run=dry_run)
        result["calendar"] = calendar
        result["calendar_spec"] = calendar_spec
        if not calendar.get("ok"):
            result["ok"] = False
            result["partial"] = True
            result["stage"] = "calendar"
            result["error"] = "Feishu calendar event was not created."
    return result


def next_start_for_schedule(schedule: dict[str, Any]) -> str:
    time_text = str(schedule.get("time") or "")
    if schedule.get("type") == "daily":
        return time_text
    if schedule.get("type") == "weekly":
        return time_text
    return time_text


def call_calendar(root: Path, spec: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    script = root / "scripts" / "create-feishu-reminder.py"
    if not script.exists():
        return {"ok": False, "error": "create-feishu-reminder.py missing"}
    argv = [sys.executable, str(script), "--spec-json", json.dumps(spec, ensure_ascii=False), "--idempotency-key", stable_id("reminder", spec), "--no-journal"]
    if dry_run:
        argv.append("--preview-spec")
    proc = subprocess.run(argv, cwd=str(root), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "result": payload}


def scheduled_spec_from_rota(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    schedule = {
        "type": "weekly",
        "day_of_week": spec.get("day_of_week"),
        "time": spec.get("time"),
        "timezone": spec.get("timezone") or "Asia/Shanghai",
        "interval": 1,
    }
    calendar_spec = {
        "task_type": "scheduled_reminder",
        "title": spec.get("title") or "值日提醒",
        "schedule": schedule,
        "message": rota_preview(spec),
        "duration_minutes": 10,
        "notify": {"mention_user": None, "create_feishu_calendar": True},
        "workspace": spec.get("workspace"),
        "attendee_ids": spec.get("attendee_ids") or [],
    }
    if not calendar_spec["attendee_ids"]:
        chat_id = workspace_chat_id(root, spec.get("workspace"))
        if chat_id:
            calendar_spec["attendee_ids"] = [chat_id]
    calendar_spec["feishu_actions"] = feishu_actions_for_spec(root, calendar_spec)
    return calendar_spec


def create_reminder_from_spec(root: Path, spec: dict[str, Any], *, dry_run: bool = False, create_calendar: bool = False) -> dict[str, Any]:
    base = workspace_root(root, spec.get("workspace"))
    store = base / "memory" / "reminders.json"
    data = load_json(store, {"reminders": []})
    reminders = data.setdefault("reminders", [])
    key = {"schedule": spec.get("schedule"), "message": spec.get("message")}
    for item in reminders:
        if item.get("status", "active") == "active" and {k: item.get(k) for k in key} == key:
            return {"ok": False, "duplicate": True, "id": item.get("id")}
    record = dict(spec)
    record.update({"id": stable_id("reminder", key), "status": "active", "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    calendar = None
    if create_calendar and (spec.get("notify") or {}).get("create_feishu_calendar"):
        calendar = call_calendar(root, spec, dry_run=dry_run)
        record["calendar"] = calendar
        if not calendar.get("ok"):
            return {
                "ok": False,
                "partial": not dry_run,
                "stage": "calendar",
                "id": record["id"],
                "path": str(store),
                "dry_run": dry_run,
                "calendar": calendar,
                "error": "Feishu calendar event was not created.",
            }
    if not dry_run:
        reminders.append(record)
        save_json(store, data)
    return {"ok": True, "id": record["id"], "path": str(store), "dry_run": dry_run, "calendar": calendar}


def preview_calendar_event_delete(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    script = root / "scripts" / "delete-feishu-reminder.py"
    if not script.exists():
        return {"ok": False, "error": "delete-feishu-reminder.py missing"}
    argv = [
        sys.executable,
        str(script),
        "--workspace",
        str(workspace_root(root, spec.get("workspace"))),
        "--event-id",
        str(spec.get("event_id")),
    ]
    proc = subprocess.run(argv, cwd=str(root), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    if proc.returncode != 0:
        return {"ok": False, "returncode": proc.returncode, "result": payload, "error": proc.stderr.strip() or proc.stdout.strip()}
    return {
        "ok": False,
        "stage": "confirm",
        "requires_confirmation": True,
        "preview": f"将取消本群已记录的飞书日程 event_id={spec.get('event_id')}。确认后执行受控删除脚本。",
        "returncode": proc.returncode,
        "result": payload,
    }


def append_memory_fact(root: Path, spec: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    base = workspace_root(root, spec.get("workspace"))
    path = base / "memory" / "facts" / "task-agent.md" if base == root else base / "memory" / "facts.md"
    line = f"- {time.strftime('%Y-%m-%d %H:%M')} {spec.get('content')}\n"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return {"ok": True, "path": str(path), "dry_run": dry_run}


def execute_spec(root: Path, spec: dict[str, Any], *, dry_run: bool = False, create_calendar: bool = False) -> dict[str, Any]:
    validation = validate_spec(spec)
    if not validation["ok"]:
        return {"ok": False, "stage": "validate", **validation}
    task_type = spec.get("task_type")
    if task_type == "weekly_rota":
        return {"stage": "execute", **create_rota_with_calendar(root, spec, dry_run=dry_run, create_calendar=create_calendar)}
    if task_type == "scheduled_reminder":
        return {"stage": "execute", **create_reminder_from_spec(root, spec, dry_run=dry_run, create_calendar=create_calendar)}
    if task_type == "calendar_event_delete":
        return preview_calendar_event_delete(root, spec)
    if task_type == "memory_write":
        return {"stage": "execute", **append_memory_fact(root, spec, dry_run=dry_run)}
    if task_type == "deploy_or_restart":
        return {"ok": False, "stage": "confirm", "requires_confirmation": True, "preview": f"将执行 {spec.get('action')} -> {spec.get('target')}，确认后才能继续。"}
    if task_type in {"file_modify_and_return", "script_create_and_run"}:
        return {"ok": False, "stage": "needs_deep_agent", "reason": "requires code generation or file editing by Codex deep agent", "spec": spec}
    return {"ok": False, "stage": "execute", "error": "unsupported task_type"}


def list_agent_tasks(root: Path, workspace: str | None) -> dict[str, Any]:
    base = workspace_root(root, workspace)
    rows: list[dict[str, Any]] = []
    for name, key in (("rotas.json", "rotas"), ("reminders.json", "reminders")):
        data = load_json(base / "memory" / name, {key: []})
        for item in data.get(key, []):
            rows.append({"id": item.get("id"), "type": item.get("task_type"), "status": item.get("status", "active"), "title": item.get("title"), "time": item.get("time") or (item.get("schedule") or {}).get("time")})
    return {"ok": True, "workspace": workspace or "private", "tasks": rows}


def handle_message(root: Path, message: str, workspace: str | None, *, source_file: str | None = None, dry_run: bool = False, create_calendar: bool = False) -> dict[str, Any]:
    route = classify_task_intent(message, workspace=workspace, root=root)
    route_data = route.to_dict()
    if route.kind != "task" or not route.task_type or route.confidence < 0.6:
        return {"ok": False, "stage": "classify", "route": route_data}
    spec = parse_task_spec(message, route.task_type, workspace or route.workspace, source_file=source_file, root=root)
    validation = validate_spec(spec)
    if not validation["ok"]:
        return {"ok": False, "stage": "validate", "route": route_data, "spec": spec, **validation}
    result = execute_spec(root, spec, dry_run=dry_run, create_calendar=create_calendar)
    return {"ok": bool(result.get("ok")), "route": route_data, "spec": spec, "result": result}


def print_text_list(data: dict[str, Any]) -> None:
    rows = data.get("tasks") or []
    title = f"自然语言任务：范围 {data.get('workspace')}"
    if not rows:
        print(title + "\n没有找到任务代理创建的任务。")
        return
    lines = [title]
    for row in rows[:20]:
        lines.append(f"- {row.get('id')} [{row.get('type')}/{row.get('status')}] {row.get('title') or ''} {row.get('time') or ''}".rstrip())
    print("\n".join(lines))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="codex-feishu natural-language task agent.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--message", default="")
    parser.add_argument("--task-type", default="")
    parser.add_argument("--source-file", default="")
    parser.add_argument("--spec-json", default="")
    parser.add_argument("--spec-file", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--create-calendar", action="store_true")
    parser.add_argument("--text", action="store_true", help="print chat-friendly text for list")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("classify")
    sub.add_parser("parse")
    sub.add_parser("validate")
    sub.add_parser("execute")
    sub.add_parser("handle")
    sub.add_parser("list")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "classify":
        result = classify_task_intent(args.message, workspace=args.workspace, root=root).to_dict()
    elif args.command == "parse":
        task_type = args.task_type or classify_task_intent(args.message, workspace=args.workspace, root=root).task_type
        if not task_type:
            result = {"ok": False, "error": "no task_type"}
        else:
            spec = parse_task_spec(args.message, task_type, args.workspace, source_file=args.source_file or None, root=root)
            result = {"ok": True, "spec": spec, "validation": validate_spec(spec)}
    elif args.command == "validate":
        spec = json.loads(args.spec_json or Path(args.spec_file).read_text(encoding="utf-8"))
        result = validate_spec(spec)
    elif args.command == "execute":
        spec = json.loads(args.spec_json or Path(args.spec_file).read_text(encoding="utf-8"))
        result = execute_spec(root, spec, dry_run=args.dry_run, create_calendar=args.create_calendar)
    elif args.command == "handle":
        result = handle_message(root, args.message, args.workspace, source_file=args.source_file or None, dry_run=args.dry_run, create_calendar=args.create_calendar)
    elif args.command == "list":
        result = list_agent_tasks(root, args.workspace)
        if args.text:
            print_text_list(result)
            return 0
    else:
        parser.print_help()
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

