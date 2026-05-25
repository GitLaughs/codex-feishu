#!/usr/bin/env python3
"""Heartbeat entrypoint for private intentions and group sensing."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SECRET_PATTERNS = [
    re.compile(r"(?i)[\"']?(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}\]\)]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]
TIME_HINT_RE = re.compile(
    r"今天|明天|后天|本周|这周|下周|周[一二三四五六日天]|"
    r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}[月/][0-9]{1,2}"
)
ABS_DATE_RE = re.compile(r"(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})-(?P<day>[0-9]{1,2})")
MONTH_DAY_RE = re.compile(r"(?P<month>[0-9]{1,2})[月/](?P<day>[0-9]{1,2})[日号]?")
CREATED_RE = re.compile(r"\bcreated:(?P<date>[0-9]{4}-[0-9]{1,2}-[0-9]{1,2})\b")
WEEKDAY_RE = re.compile(r"(?P<prefix>本周|这周|下周)?周(?P<day>[一二三四五六日天])")
WEEKDAY_INDEX = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def display_line(line: str, max_len: int = 360) -> str:
    value = re.sub(r"<!--.*?-->", "", line)
    value = re.sub(r"^\s*-\s*\[[^\]]+\]\s*(\[[^\]]+\]\s*){0,3}", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = redact(value)
    if len(value) > max_len:
        value = value[:max_len] + "..."
    return value


def display_child_line(line: str, max_len: int = 300) -> str:
    value = display_line(line, max_len=max_len)
    if value.startswith(("group_sense=", "reminder_candidate ")):
        return value
    if value.startswith(("dry_run add ", "reminder root=")):
        return ""
    return f"group_sense=detail {value}"


def ordered_unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def read_json(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        return {}, True
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), True
    except Exception:
        return {}, False


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def created_date(line: str) -> date | None:
    match = CREATED_RE.search(line)
    if not match:
        return None
    return parse_date(match.group("date"))


def strip_comments(line: str) -> str:
    return re.sub(r"<!--.*?-->", "", line)


def current_weekday_delta(anchor: date, target_weekday: int) -> int:
    return target_weekday - anchor.weekday()


def next_weekday_delta(anchor: date, target_weekday: int) -> int:
    delta = target_weekday - anchor.weekday()
    if delta < 0:
        delta += 7
    return delta


def add_relative_dates(line: str, created: date, dates: list[date]) -> None:
    body = strip_comments(line)
    matched_weekday = False

    for match in WEEKDAY_RE.finditer(body):
        matched_weekday = True
        target_weekday = WEEKDAY_INDEX[match.group("day")]
        prefix = match.group("prefix") or ""
        if prefix == "下周":
            delta = 7 - created.weekday() + target_weekday
        elif prefix in ("本周", "这周"):
            delta = current_weekday_delta(created, target_weekday)
        else:
            delta = next_weekday_delta(created, target_weekday)
        dates.append(created + timedelta(days=delta))

    if "今天" in body:
        dates.append(created)
    if "明天" in body:
        dates.append(created + timedelta(days=1))
    if "后天" in body:
        dates.append(created + timedelta(days=2))
    if "周末" in body:
        dates.append(created + timedelta(days=current_weekday_delta(created, 6)))
    if re.search(r"本周|这周", body) and not matched_weekday:
        dates.append(created + timedelta(days=current_weekday_delta(created, 6)))
    if "下周" in body and not matched_weekday:
        dates.append(created + timedelta(days=13 - created.weekday()))


def latest_due_date(line: str, today: date) -> date | None:
    dates: list[date] = []
    body = strip_comments(line)
    for match in ABS_DATE_RE.finditer(body):
        try:
            dates.append(date(int(match.group("year")), int(match.group("month")), int(match.group("day"))))
        except ValueError:
            pass
    for match in MONTH_DAY_RE.finditer(body):
        try:
            candidate = date(today.year, int(match.group("month")), int(match.group("day")))
            if candidate < today:
                candidate = date(today.year + 1, int(match.group("month")), int(match.group("day")))
            dates.append(candidate)
        except ValueError:
            pass

    created = created_date(line)
    if created:
        add_relative_dates(line, created, dates)

    if not dates:
        return None
    return max(dates)


def should_surface_task(line: str, today: date) -> bool:
    if not TIME_HINT_RE.search(line):
        return False
    due = latest_due_date(line, today)
    if due is None:
        # Relative-only legacy lines are ambiguous and cause stale reminders.
        return False
    return today <= due


def task_lines(root: Path, today: date) -> list[str]:
    out: list[str] = []
    for rel in ("memory/tasks/open.md", "memory/facts/intentions.md"):
        path = root / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not re.match(r"^\s*-\s+", line):
                continue
            if "<!-- status:done" in line:
                continue
            if should_surface_task(line, today):
                out.append(line)
    return out


def today_lark_event_message_count(group: Path, today: date, limit: int) -> int:
    event_dir = group / "memory" / "lark-events"
    if not event_dir.exists():
        return 0
    count = 0
    files = sorted(event_dir.glob("*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]
    for path in files:
        try:
            if datetime.fromtimestamp(path.stat().st_mtime).date() != today:
                continue
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
        except OSError:
            continue
        count += sum(1 for line in lines if line.strip())
    return count


def has_group_summary(group: Path, today: date) -> bool:
    path = group / "memory" / "summaries" / f"{today.isoformat()}.md"
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "[summary/3]" in text and "[group-sense]" in text


def run_private_curator(root: Path, today: date, dry_run: bool, timeout: int) -> list[str]:
    script = Path(__file__).with_name("memory-curator.py")
    inbox_dir = root / "memory" / "inbox"
    inbox_paths = sorted(inbox_dir.glob(f"{today.isoformat()}-private-messages*.jsonl")) if inbox_dir.exists() else []
    if not script.exists() or not inbox_paths:
        return []
    cmd = [
        sys.executable,
        str(script),
        "--workspace",
        str(root),
        "--date",
        today.isoformat(),
    ]
    if dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [f"private_curator=error reason=timeout"]
    except OSError as exc:
        return [f"private_curator=error reason=spawn_failed detail={display_line(str(exc), 120)}"]

    out: list[str] = []
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        safe_line = display_line(line, max_len=220)
        if not safe_line or safe_line.startswith("No inbox:"):
            continue
        out.append(f"private_curator=detail {safe_line}")
    if proc.returncode != 0:
        out.append(f"private_curator=error exit={proc.returncode}")
    return out


def run_packet_builder(script_name: str, args: list[str], timeout: int) -> list[str]:
    script = Path(__file__).with_name(script_name)
    if not script.exists():
        return [f"evidence_packet=error script={script_name} reason=missing"]
    cmd = [sys.executable, str(script), *args]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [f"evidence_packet=error script={script_name} reason=timeout"]
    except OSError as exc:
        return [f"evidence_packet=error script={script_name} reason=spawn_failed detail={display_line(str(exc), 120)}"]
    out: list[str] = []
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        safe = display_line(line, max_len=260)
        if safe:
            out.append(f"evidence_packet=detail {safe}")
    if proc.returncode != 0:
        out.append(f"evidence_packet=error script={script_name} exit={proc.returncode}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=str(Path.cwd()))
    parser.add_argument("--group-workspace", action="append", default=[])
    parser.add_argument("--recent-limit", type=int, default=120)
    parser.add_argument("--summary-trigger-messages", type=int, default=12)
    parser.add_argument("--group-timeout-seconds", type=int, default=20)
    parser.add_argument("--curator-timeout-seconds", type=int, default=20)
    parser.add_argument("--no-curate-private-inbox", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--today")
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    today = parse_date(args.today) if args.today else datetime.now().date()
    if today is None:
        raise SystemExit("--today must use YYYY-MM-DD")
    default_groups = []
    groups = [Path(item).resolve() for item in args.group_workspace]
    if not groups:
        groups = [root / item for item in default_groups]

    state_path = root / "memory" / "heartbeat-state.json"
    state, state_ok = read_json(state_path)
    assistant = state.setdefault("assistantSense", {})
    existing_hashes = ordered_unique([str(x) for x in assistant.get("recentReminderHashes", [])])
    seen = set(existing_hashes)
    new_hashes: list[str] = []

    script = Path(__file__).with_name("codex-feishu-group-sense.py")
    sense_output: list[str] = []
    if not args.no_curate_private_inbox:
        sense_output.extend(run_private_curator(root, today, args.dry_run, args.curator_timeout_seconds))
        if not args.dry_run:
            sense_output.extend(
                run_packet_builder(
                    "build-feishu-private-packet.py",
                    ["--workspace", str(root), "--date", today.isoformat()],
                    args.curator_timeout_seconds,
                )
            )

    for group in groups:
        if not group.exists():
            continue
        event_count = today_lark_event_message_count(group, today, args.recent_limit)
        summary_trigger = (
            args.summary_trigger_messages > 0
            and event_count >= args.summary_trigger_messages
            and not has_group_summary(group, today)
        )
        min_summary_messages = (
            args.summary_trigger_messages
            if summary_trigger
            else max(args.recent_limit + 1, args.summary_trigger_messages + 1)
        )
        if summary_trigger:
            sense_output.append(
                f"group_summary_trigger=run workspace={group} messages={event_count} "
                f"threshold={args.summary_trigger_messages}"
            )
        cmd = [
            sys.executable,
            str(script),
            "--workspace",
            str(group),
            "--recent-limit",
            str(args.recent_limit),
            "--min-summary-messages",
            str(min_summary_messages),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        try:
            proc = subprocess.run(
                cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=args.group_timeout_seconds,
            )
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    safe_line = display_child_line(line)
                    if safe_line:
                        sense_output.append(safe_line)
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    safe_line = display_child_line(line)
                    if safe_line:
                        sense_output.append(safe_line)
            if proc.returncode != 0:
                sense_output.append(f"group_sense=error workspace={group} exit={proc.returncode}")
        except subprocess.TimeoutExpired:
            sense_output.append(f"group_sense=error workspace={group} reason=timeout")
        except OSError as exc:
            sense_output.append(f"group_sense=error workspace={group} reason=spawn_failed detail={display_line(str(exc), 120)}")

    reminders: list[tuple[str, str]] = []
    if state_ok:
        roots = [root] + [g for g in groups if g.exists()]
        for item_root in roots:
            for line in task_lines(item_root, today):
                key = stable_hash(f"{item_root}:{line}")
                if key in seen:
                    continue
                seen.add(key)
                new_hashes.append(key)
                reminders.append((str(item_root), display_line(line)))
    else:
        sense_output.append("assistant_sense=state_error reason=invalid_json reminders_suppressed=1")

    if not args.dry_run and state_ok:
        assistant["lastRunIso"] = datetime.now().astimezone().isoformat()
        assistant["recentReminderHashes"] = ordered_unique(existing_hashes + new_hashes)[-200:]
        write_json(state_path, state)

    if reminders:
        print(f"assistant_sense=attention reminders={len(reminders)}")
        for root_text, line in reminders[:8]:
            print(f"reminder root={root_text} text={line}")
    else:
        print("assistant_sense=ok reminders=0")
    for line in sense_output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

