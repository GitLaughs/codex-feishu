#!/usr/bin/env python3
"""Focused tests for codex-feishu natural-language task agent."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "task-agent.py"
COMMAND = ROOT / "scripts" / "codex-feishu-command.py"


def run(args: list[str], *, cwd: Path | None = None, ok: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ok and proc.returncode != 0:
        raise SystemExit(f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load_json(proc: subprocess.CompletedProcess) -> dict:
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"bad json: {proc.stdout}\nstderr={proc.stderr}") from exc


def make_workspace(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "workspace_manifest.json").write_text(
        json.dumps(
            {"schema_version": 1, "workspace": name, "scope": "test", "feishu": {"chat_id": "oc_test_chat"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    temp = ROOT / ".tmp" / f"task-agent-test-{uuid.uuid4().hex[:8]}"
    workspace = f"任务代理测试-{uuid.uuid4().hex[:6]}"
    try:
        make_workspace(temp, workspace)

        fixed = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", "/files find SC132GS", "classify"]))
        if fixed.get("kind") != "command":
            raise SystemExit(f"fixed command misclassified: {fixed}")

        msg = "整体值日顺序：洗手台、拖地、厕所、轮休。本周：小明 洗手台，小红 拖地，小李 厕所，小王 轮休。每周日晚上7点提醒"
        parsed = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", msg, "parse"]))
        spec = parsed["spec"]
        if spec["task_type"] != "weekly_rota" or spec["day_of_week"] != 0 or spec["time"] != "19:00":
            raise SystemExit(f"rota parse failed: {parsed}")
        if parsed["validation"]["ok"] is not True:
            raise SystemExit(f"rota validation failed: {parsed}")
        actions = spec.get("feishu_actions") or []
        if not any(item.get("service") == "calendar" and item.get("attendee_ids") == ["oc_test_chat"] for item in actions):
            raise SystemExit(f"rota did not map to Feishu calendar action: {parsed}")

        handled = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", msg, "handle"]))
        if not handled.get("ok"):
            raise SystemExit(f"rota handle failed: {handled}")
        rota_path = temp / workspace / "memory" / "rotas.json"
        if not rota_path.exists() or "小明" not in rota_path.read_text(encoding="utf-8"):
            raise SystemExit("rota store not written")

        duplicate = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", msg, "handle"], ok=False))
        if duplicate.get("result", {}).get("duplicate") is not True:
            raise SystemExit(f"duplicate rota not detected: {duplicate}")

        missing = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", "每周日提醒值日", "handle"], ok=False))
        if "还缺提醒时间" not in missing.get("question", ""):
            raise SystemExit(f"missing field question failed: {missing}")

        reminder = load_json(run([str(SCRIPT), "--root", str(temp), "--message", "每天晚上9点提醒我检查服务器余额", "handle"]))
        if not reminder.get("ok"):
            raise SystemExit(f"reminder handle failed: {reminder}")
        if not (temp / "memory" / "reminders.json").exists():
            raise SystemExit("reminder store not written")

        delete_msg = "尝试删除event_id b198c46e-9b39-449e-a525-78f40c5e49b9_0"
        delete_route = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", delete_msg, "classify"]))
        if delete_route.get("task_type") != "calendar_event_delete":
            raise SystemExit(f"calendar delete misclassified: {delete_route}")
        delete_parse = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", delete_msg, "parse"]))
        delete_spec = delete_parse["spec"]
        if delete_spec.get("event_id") != "b198c46e-9b39-449e-a525-78f40c5e49b9_0" or delete_parse["validation"]["ok"] is not True:
            raise SystemExit(f"calendar delete parse failed: {delete_parse}")

        calendar_spec = {
            "task_type": "scheduled_reminder",
            "title": "巡检提醒",
            "schedule": {"type": "weekly", "day_of_week": 0, "time": "19:00", "timezone": "Asia/Shanghai"},
            "message": "本周巡检",
            "attendee_ids": ["oc_test_chat"],
        }
        preview = load_json(
            run(
                [
                    str(ROOT / "scripts" / "create-feishu-reminder.py"),
                    "--spec-json",
                    json.dumps(calendar_spec, ensure_ascii=False),
                    "--preview-spec",
                ]
            )
        )
        if preview.get("rrule") != "FREQ=WEEKLY;INTERVAL=1;BYDAY=SU" or preview.get("attendee_ids") != ["oc_test_chat"]:
            raise SystemExit(f"calendar spec preview failed: {preview}")

        file_task = load_json(run([str(SCRIPT), "--root", str(temp), "--workspace", workspace, "--message", "帮我把这个 py 脚本改成只能读取 localhost 和本地文件，改好发回来", "handle"], ok=False))
        if file_task.get("question") != "还缺要修改的文件：请上传文件或给出 local_files 路径。":
            raise SystemExit(f"file missing source question failed: {file_task}")

        cmd = run([str(COMMAND), "--root", str(temp), "--workspace", workspace, "/task", "preview", msg])
        if "任务代理预览" not in cmd.stdout or "weekly_rota" not in cmd.stdout:
            raise SystemExit(f"/task preview failed: {cmd.stdout}\n{cmd.stderr}")

        listed = run([str(COMMAND), "--root", str(temp), "--workspace", workspace, "/task", "list"])
        if "自然语言任务" not in listed.stdout or "rota-" not in listed.stdout:
            raise SystemExit(f"/task list failed: {listed.stdout}\n{listed.stderr}")

        print("task_agent_tests=ok")
        return 0
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

