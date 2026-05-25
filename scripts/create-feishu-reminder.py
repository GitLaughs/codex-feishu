#!/usr/bin/env python
"""Create a Feishu calendar reminder through lark-cli.

Examples:
  python scripts/create-feishu-reminder.py --summary "喝水" --start "07:06"
  python scripts/create-feishu-reminder.py --summary "擦药" --start "2026-05-24 22:30" --duration 10
  python scripts/create-feishu-reminder.py --summary "喝水" --start "明天 09:00" --description "起床后喝水"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "work" / "cache" / "feishu-primary-calendar.json"
DAILY_NOTE = ROOT / "scripts" / "daily-note.ps1"


def lark_cli() -> list[str]:
    override = os.environ.get("CODEX_FEISHU_LARK_CLI_BIN", "").strip()
    if override:
        return [override]

    command = shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or shutil.which("lark-cli.ps1")
    if not command:
        raise RuntimeError("lark-cli not found in PATH.")
    return [command]


def run_json(argv: list[str]) -> Dict[str, Any]:
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
        json_start_candidates = [pos for pos in (output.find("{"), output.find("[")) if pos >= 0]
        if json_start_candidates:
            json_start = min(json_start_candidates)
            decoder = json.JSONDecoder()
            try:
                payload, _ = decoder.raw_decode(output[json_start:])
                return payload
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"lark-cli returned non-JSON output: {output[:500]}") from exc


def get_primary_calendar_id(refresh: bool = False) -> str:
    if not refresh and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            calendar_id = cached.get("calendar_id")
            if isinstance(calendar_id, str) and calendar_id:
                return calendar_id
        except Exception:
            pass

    data = run_json([*lark_cli(), "calendar", "calendars", "primary", "--as", "user"])
    calendars = data.get("data", {}).get("calendars", [])
    if not calendars:
        raise RuntimeError("No primary calendar returned by lark-cli.")
    calendar = calendars[0].get("calendar", {})
    calendar_id = calendar.get("calendar_id")
    if not calendar_id:
        raise RuntimeError("Primary calendar response did not include calendar_id.")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(
            {
                "calendar_id": calendar_id,
                "summary": calendar.get("summary", ""),
                "updated_at": datetime.now(SHANGHAI).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return calendar_id


def parse_start(value: str, now: Optional[datetime] = None) -> datetime:
    raw = value.strip()
    now = now or datetime.now(SHANGHAI)

    prefix_days = {
        "今天": 0,
        "今日": 0,
        "明天": 1,
        "明日": 1,
        "后天": 2,
    }
    for prefix, days in prefix_days.items():
        if raw.startswith(prefix):
            time_text = raw[len(prefix) :].strip()
            base = now.date() + timedelta(days=days)
            return combine_date_time(str(base), time_text)

    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        return combine_date_time(str(now.date()), raw)

    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}", raw):
        date_text, time_text = raw.split()
        return combine_date_time(date_text, time_text)

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            "Unsupported time. Use HH:MM, 今日 HH:MM, 明天 HH:MM, "
            "YYYY-MM-DD HH:MM, or ISO 8601."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def combine_date_time(date_text: str, time_text: str) -> datetime:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", time_text)
    if not match:
        raise ValueError(f"Invalid time of day: {time_text!r}")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"Invalid time of day: {time_text!r}")
    date_parts = [int(part) for part in date_text.split("-")]
    return datetime(date_parts[0], date_parts[1], date_parts[2], hour, minute, tzinfo=SHANGHAI)


def validate_reminder_spec(spec: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("task_type") != "scheduled_reminder":
        errors.append("task_type must be scheduled_reminder")
    schedule = spec.get("schedule")
    if not isinstance(schedule, dict):
        errors.append("schedule must be an object")
        schedule = {}
    if not spec.get("title"):
        errors.append("title is required")
    if not spec.get("message"):
        errors.append("message is required")
    if not re.fullmatch(r"\d{2}:\d{2}", str(schedule.get("time") or "")):
        errors.append("schedule.time must be HH:MM")
    if schedule.get("type") not in {"once", "daily", "weekly"}:
        errors.append("schedule.type must be once, daily, or weekly")
    if schedule.get("type") == "weekly" and schedule.get("day_of_week") not in range(7):
        errors.append("schedule.day_of_week must be 0-6 for weekly reminders")
    attendees = spec.get("attendee_ids") or []
    if attendees and not isinstance(attendees, list):
        errors.append("attendee_ids must be a list")
    for attendee in attendees if isinstance(attendees, list) else []:
        value = str(attendee)
        if not (value.startswith(("ou_", "oc_", "omm_")) or "@" in value):
            errors.append(f"unsupported attendee id: {value}")
    return errors


def next_occurrence_from_spec(spec: Dict[str, Any], now: Optional[datetime] = None) -> datetime:
    schedule = spec.get("schedule") or {}
    now = now or datetime.now(SHANGHAI)
    time_text = str(schedule.get("time") or "")
    base = combine_date_time(str(now.date()), time_text)
    if schedule.get("type") == "weekly":
        target = int(schedule.get("day_of_week"))
        days = (target - ((now.weekday() + 1) % 7)) % 7
        if days == 0 and base <= now:
            days = 7
        return combine_date_time(str(now.date() + timedelta(days=days)), time_text)
    if base <= now:
        base += timedelta(days=1)
    return base


def preview_reminder(spec: Dict[str, Any]) -> Dict[str, Any]:
    errors = validate_reminder_spec(spec)
    if errors:
        return {"ok": False, "errors": errors}
    start = next_occurrence_from_spec(spec)
    rrule = recurrence_from_spec(spec)
    return {
        "ok": True,
        "summary": spec.get("title"),
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=int(spec.get("duration_minutes") or 5))).isoformat(),
        "rrule": rrule,
        "attendee_ids": spec.get("attendee_ids") or [],
        "message": spec.get("message"),
        "schedule": spec.get("schedule"),
    }


def recurrence_from_spec(spec: Dict[str, Any]) -> str:
    schedule = spec.get("schedule") or {}
    interval = int(schedule.get("interval") or 1)
    if schedule.get("type") == "daily":
        return f"FREQ=DAILY;INTERVAL={interval}"
    if schedule.get("type") == "weekly":
        day = schedule.get("day_of_week")
        byday = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"][int(day)]
        return f"FREQ=WEEKLY;INTERVAL={interval};BYDAY={byday}"
    return ""


def spec_to_args(spec: Dict[str, Any], args: argparse.Namespace) -> argparse.Namespace:
    errors = validate_reminder_spec(spec)
    if errors:
        raise ValueError("; ".join(errors))
    start = next_occurrence_from_spec(spec)
    return argparse.Namespace(
        summary=str(spec.get("title")),
        start=start.strftime("%Y-%m-%d %H:%M"),
        description=str(spec.get("message") or ""),
        duration=int(spec.get("duration_minutes") or args.duration),
        reminder_minutes=args.reminder_minutes,
        visibility=args.visibility,
        busy_status=args.busy_status,
        calendar_id=args.calendar_id,
        refresh_calendar=args.refresh_calendar,
        idempotency_key=args.idempotency_key or "",
        rrule=str(spec.get("rrule") or recurrence_from_spec(spec)),
        attendee_ids=",".join(str(item) for item in (spec.get("attendee_ids") or [])),
        allow_past=False,
        dry_run=args.dry_run,
        no_journal=args.no_journal,
    )


def create_reminder_from_spec(spec: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    return create_event(spec_to_args(spec, args))


def create_event(args: argparse.Namespace) -> Dict[str, Any]:
    start = parse_start(args.start)
    now = datetime.now(SHANGHAI)
    if start < now and not args.allow_past:
        raise RuntimeError(
            f"Start time is in the past: {start.isoformat()}. "
            "Pass --allow-past only if this is intentional."
        )

    end = start + timedelta(minutes=args.duration)
    argv = [
        *lark_cli(),
        "calendar",
        "+create",
        "--as",
        "user",
        "--summary",
        args.summary,
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--description",
        args.description or "",
    ]
    if args.calendar_id:
        argv.extend(["--calendar-id", args.calendar_id])
    if args.rrule:
        argv.extend(["--rrule", args.rrule])
    if args.attendee_ids:
        argv.extend(["--attendee-ids", args.attendee_ids])
    if args.dry_run:
        argv.append("--dry-run")

    result = run_json(argv)
    event = result.get("data", {}).get("event", {})
    if event and not args.dry_run and not args.no_journal:
        write_journal(args.summary, start, end, event.get("event_id", ""))
    return result


def parse_attendee_ids(value: str) -> list[Dict[str, Any]]:
    attendees: list[Dict[str, Any]] = []
    for raw in [part.strip() for part in str(value or "").split(",") if part.strip()]:
        if raw.startswith("ou_"):
            attendees.append({"type": "user", "user_id": raw})
        elif raw.startswith("oc_"):
            attendees.append({"type": "chat", "chat_id": raw})
        elif raw.startswith("omm_"):
            attendees.append({"type": "resource", "room_id": raw})
        elif "@" in raw:
            attendees.append({"type": "third_party", "third_party_email": raw})
    return attendees


def add_event_attendees(calendar_id: str, event_id: str, attendees: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not event_id:
        raise RuntimeError("calendar event did not include event_id for attendee creation")
    params = {"calendar_id": calendar_id, "event_id": event_id, "user_id_type": "open_id"}
    body = {"attendees": attendees, "need_notification": True}
    return run_json(
        [
            *lark_cli(),
            "calendar",
            "event.attendees",
            "create",
            "--as",
            "user",
            "--params",
            json.dumps(params, ensure_ascii=False, separators=(",", ":")),
            "--data",
            json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def write_journal(summary: str, start: datetime, end: datetime, event_id: str) -> None:
    if not DAILY_NOTE.exists():
        return
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        return
    text = (
        f"已通过 create-feishu-reminder.py 创建飞书日程提醒："
        f"{start.strftime('%Y-%m-%d %H:%M')}-{end.strftime('%H:%M')}，"
        f"标题“{summary}”，event_id={event_id}。"
    )
    subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DAILY_NOTE),
            "-Text",
            text,
            "-Task",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a fast Feishu calendar reminder.")
    parser.add_argument("--summary", default="", help="Event title, for example 喝水.")
    parser.add_argument("--start", default="", help="HH:MM, 今日 HH:MM, 明天 HH:MM, YYYY-MM-DD HH:MM, or ISO.")
    parser.add_argument("--description", default="", help="Optional event description.")
    parser.add_argument("--duration", type=int, default=5, help="Duration in minutes. Default: 5.")
    parser.add_argument("--reminder-minutes", type=int, default=0, help="Reminder offset before start. Default: 0.")
    parser.add_argument("--visibility", choices=["default", "public", "private"], default="private")
    parser.add_argument("--busy-status", choices=["free", "busy"], default="free")
    parser.add_argument("--calendar-id", default=os.environ.get("FEISHU_CALENDAR_ID", ""), help="Override calendar_id.")
    parser.add_argument("--refresh-calendar", action="store_true", help="Refresh cached primary calendar id.")
    parser.add_argument("--idempotency-key", default="", help="Optional Feishu idempotency key.")
    parser.add_argument("--rrule", default="", help="RFC5545 recurrence rule, for example FREQ=WEEKLY;INTERVAL=1.")
    parser.add_argument("--attendee-ids", default="", help="Comma-separated Feishu attendees: ou_, oc_, omm_, or email.")
    parser.add_argument("--allow-past", action="store_true", help="Allow creating an event in the past.")
    parser.add_argument("--dry-run", action="store_true", help="Print lark-cli dry-run result without creating.")
    parser.add_argument("--no-journal", action="store_true", help="Do not append local codex-feishu journal entry.")
    parser.add_argument("--spec-json", default="", help="scheduled_reminder JSON spec.")
    parser.add_argument("--spec-file", default="", help="Path to scheduled_reminder JSON spec.")
    parser.add_argument("--preview-spec", action="store_true", help="Validate and preview the spec without creating.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    spec: Dict[str, Any] | None = None
    if args.spec_json or args.spec_file:
        try:
            spec = json.loads(args.spec_json or Path(args.spec_file).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR: invalid spec: {exc}", file=sys.stderr)
            return 1
        if args.preview_spec:
            print(json.dumps(preview_reminder(spec), ensure_ascii=False, indent=2))
            return 0
    elif not args.summary or not args.start:
        parser.error("--summary and --start are required unless --spec-json or --spec-file is used")

    try:
        result = create_reminder_from_spec(spec, args) if spec is not None else create_event(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    event = result.get("data", {}).get("event", {})
    if event:
        print(
            json.dumps(
                {
                    "ok": True,
                    "event_id": event.get("event_id"),
                    "summary": event.get("summary"),
                    "start_time": event.get("start_time"),
                    "end_time": event.get("end_time"),
                    "app_link": event.get("app_link"),
                    "dry_run": bool(args.dry_run),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

