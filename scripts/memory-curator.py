#!/usr/bin/env python3
"""Promote private inbox messages into structured codex-feishu memory files."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
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

DEFAULT_TRIGGERS: dict[str, list[str]] = {
    "preference": ["remember", "preference", "prefer", "rule", "always", "never", "以后", "记住", "偏好", "喜欢", "不喜欢", "习惯", "规则", "以后别", "以后要"],
    "task": ["deadline", "ddl", "due", "remind", "tomorrow", "today", "next week", "calendar", "meeting", "todo", "task", "截止", "提醒", "明天", "今天", "后天", "下周", "日程", "会议", "待办", "任务"],
    "emotion": ["tired", "stress", "stressed", "sad", "happy", "angry", "anxious", "rushed", "blocked", "累", "烦", "焦虑", "紧张", "难受", "开心", "高兴", "生气", "崩溃", "emo", "压力", "困", "睡不着", "来不及", "熬夜", "撑不住", "赶ddl", "卡住"],
    "intent": ["想", "打算", "准备", "可能要", "预计", "希望", "考虑", "下次", "过几天", "到时候", "下周", "周末", "出差", "早会", "考试", "汇报"],
    "relationship": ["负责", "组长", "队长", "老师", "导师", "评审", "同学", "队友", "协作", "对接", "模块", "分工"],
    "decision": ["decision", "decided", "plan", "方案", "决定", "计划", "定了", "改成", "采用", "不再"],
    "project": ["project", "repo", "code", "file", "doc", "report", "codex-feishu", "项目", "仓库", "代码", "文件", "文档", "报告"],
    "people": ["person", "people", "teammate", "teacher", "同学", "老师", "队友", "负责人"],
    "important": ["must", "important", "critical", "urgent", "必须", "重要", "紧急", "别忘", "一定"],
}

MOOD_TEMPLATE = [
    "Use this only for patterns that are useful later, not for every passing emotion.",
    "Do not store raw private text, secrets, credentials, or private identifiers.",
    "Entry format:",
    "`- [HH:mm:ss] [emotion/N] [inbox] labels:<label,...>; persistence:<single_signal|recurring_or_timed>; summary:<redacted summary> <!-- source:<hash> -->`",
]

INTENTIONS_TEMPLATE = [
    "Informal future plans the human mentioned in private chat.",
    "These are softer than tasks. Use them for heartbeat reminders only when the timing is relevant and the reminder would be useful.",
    "Do not store secrets, raw identifiers, or sensitive message text.",
    "Entry format:",
    "`- [HH:mm:ss] [intent/N] [inbox] <redacted plan> <!-- source:<hash> created:YYYY-MM-DD -->`",
    "Close or supersede stale items by adding `status:done` or a newer entry rather than deleting history.",
]


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> tuple[str, bool]:
    value = str(text)
    redacted = False
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            redacted = True
            value = pattern.sub("[REDACTED]", value)
    return value, redacted


def ensure_file(path: Path, title: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {title}\n\n", encoding="utf-8")


def ensure_template(path: Path, title: str, required_lines: list[str]) -> None:
    ensure_file(path, title)
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [line for line in required_lines if line and line.lower() not in text.lower()]
    if missing:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n")
            for line in required_lines:
                handle.write(line + "\n")


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def append_once(path: Path, line: str, marker: str) -> bool:
    if path.exists() and marker.lower() in path.read_text(encoding="utf-8", errors="ignore").lower():
        return False
    append_line(path, line)
    return True


def load_triggers(workspace: Path) -> dict[str, list[str]]:
    merged = {key: list(values) for key, values in DEFAULT_TRIGGERS.items()}
    path = workspace / "memory" / "triggers.json"
    if not path.exists():
        return merged
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return merged
    if not isinstance(data, dict):
        return merged
    for key, values in data.items():
        if key not in merged:
            continue
        if not isinstance(values, list):
            continue
        seen = {item.lower() for item in merged[key]}
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            lowered = value.lower()
            if lowered not in seen:
                merged[key].append(value)
                seen.add(lowered)
    return merged


def trigger_match(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term and term.lower() in lowered for term in terms)


def category_for(text: str, triggers: dict[str, list[str]]) -> str:
    for category in ("preference", "emotion", "relationship", "intent", "task", "decision", "project", "people"):
        if trigger_match(text, triggers.get(category, [])):
            return category
    if re.search(r"(?i)\b(i feel|i am feeling|felt)\b|我(有点|很|真的)?(累|烦|慌|怕|开心|难受|焦虑|紧张)", text):
        return "emotion"
    if re.search(r"(我|我们).{0,8}(想|打算|准备|计划|可能要|预计|希望|考虑)", text):
        return "intent"
    if re.search(r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}).{0,6}(负责|对接|协作|组长|队长|老师|导师)", text):
        return "relationship"
    return "note"


def importance_for(category: str, text: str, triggers: dict[str, list[str]]) -> int:
    score = 1
    if category in {"preference", "task", "decision"}:
        score += 2
    if category in {"emotion", "intent", "relationship"}:
        score += 2
    if category in {"project", "people"}:
        score += 1
    if trigger_match(text, triggers.get("important", [])):
        score += 2
    if len(text) > 80:
        score += 1
    if category == "emotion" and re.search(r"连续|一直|又|最近|今天|今晚|这几天|睡不着|来不及|崩溃", text):
        score += 1
    if category == "intent" and re.search(r"今天|明天|后天|下周|周末|[0-9]{1,2}[月/][0-9]{1,2}|[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        score += 1
    return min(score, 5)


def mood_labels(text: str) -> list[str]:
    patterns = {
        "tired": r"(?i)tired|sleepy|exhausted|累|困|熬夜|没睡|睡不着|撑不住",
        "anxious": r"(?i)anxious|stress|stressed|焦虑|紧张|慌|压力|担心|怕",
        "rushed": r"(?i)rushed|deadline|ddl|urgent|来不及|赶|急|截止",
        "blocked": r"(?i)blocked|stuck|卡住|没思路|不会弄|走不动|没进展",
        "frustrated": r"(?i)frustrated|angry|烦|生气|崩溃|难受|emo",
        "happy": r"(?i)happy|glad|开心|高兴|舒服|爽",
        "relieved": r"(?i)relieved|放松|松口气|终于好了|稳了",
        "proud": r"(?i)proud|有成就感|做成了|搞定了",
    }
    labels = [label for label, pattern in patterns.items() if re.search(pattern, text)]
    return labels or ["mood"]


def mood_summary(text: str) -> str:
    persistence = "recurring_or_timed" if re.search(r"连续|一直|又|最近|今天|今晚|这几天|睡不着|熬夜|撑不住|来不及|崩溃", text) else "single_signal"
    return f"labels:{','.join(mood_labels(text))}; persistence:{persistence}; summary:private-chat mood signal"


def memory_line(time: str, category: str, importance: int, source: str, text: str) -> str:
    return f"- [{time}] [{category}/{importance}] [{source}] {text}"


def curate(workspace: Path, date_text: str, dry_run: bool = False, show_items: bool = False) -> tuple[int, int]:
    memory = workspace / "memory"
    inbox = memory / "inbox"
    facts = memory / "facts"
    projects = memory / "projects"
    people = memory / "people"
    tasks = memory / "tasks"
    daily_dir = memory / "daily"
    for path in (memory, inbox, facts, projects, people, tasks, daily_dir):
        path.mkdir(parents=True, exist_ok=True)

    inbox_paths = sorted(inbox.glob(f"{date_text}-private-messages*.jsonl"))
    if not inbox_paths:
        print(f"No inbox: {inbox / f'{date_text}-private-messages.jsonl'}")
        return 0, 0

    daily_path = daily_dir / f"{date_text}.md"
    legacy_daily_path = memory / f"{date_text}.md"
    processed_path = inbox / f"{date_text}-curated.txt"
    processed = set(processed_path.read_text(encoding="utf-8", errors="ignore").splitlines()) if processed_path.exists() else set()

    ensure_file(daily_path, f"{date_text} Daily")
    ensure_file(facts / "profile.md", "Profile Facts")
    ensure_file(facts / "rules.md", "Rules")
    ensure_template(facts / "mood.md", "Mood Signals", MOOD_TEMPLATE)
    ensure_template(facts / "intentions.md", "Intentions", INTENTIONS_TEMPLATE)
    ensure_file(projects / "INDEX.md", "Projects")
    ensure_file(people / "INDEX.md", "People")
    ensure_file(tasks / "open.md", "Open Tasks")

    triggers = load_triggers(workspace)
    count = 0
    promoted = 0
    daily_text = daily_path.read_text(encoding="utf-8", errors="ignore")

    for inbox_path in inbox_paths:
        for raw in inbox_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not raw.strip():
                continue
            source_hash = stable_hash(raw)
            if source_hash in processed:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            text = item.get("text", "") if isinstance(item, dict) else ""
            if not isinstance(text, str) or not text.strip():
                continue
            safe_text, _ = redact(text)
            category = category_for(safe_text, triggers)
            importance = importance_for(category, safe_text, triggers)
            time_text = str(item.get("time") or "00:00:00")
            line = memory_line(time_text, category, importance, "inbox", safe_text)
            count += 1

            if dry_run:
                if show_items:
                    print(line)
                continue

            if safe_text.lower() not in daily_text.lower():
                append_line(daily_path, line)
                daily_text += "\n" + line

            if importance >= 3 or category != "note":
                promoted += 1
                marker = f"source:{source_hash}"
                if category == "preference":
                    target = facts / ("rules.md" if re.search(r"(?i)rule|always|never|必须|不要|规则|以后别|以后要", safe_text) else "profile.md")
                    append_once(target, f"{line} <!-- {marker} -->", marker)
                elif category == "task":
                    append_once(tasks / "open.md", f"{line} <!-- status:open {marker} created:{date_text} -->", marker)
                elif category == "project":
                    append_once(projects / "INDEX.md", f"{line} <!-- {marker} -->", marker)
                elif category in {"people", "relationship"}:
                    append_once(people / "INDEX.md", f"{line} <!-- {marker} -->", marker)
                elif category == "emotion":
                    mood_line = memory_line(time_text, category, importance, "inbox", mood_summary(safe_text))
                    append_once(facts / "mood.md", f"{mood_line} <!-- {marker} -->", marker)
                elif category == "intent":
                    append_once(facts / "intentions.md", f"{line} <!-- {marker} -->", marker)
                    if re.search(r"今天|明天|后天|下周|周末|[0-9]{1,2}[月/][0-9]{1,2}|[0-9]{4}-[0-9]{2}-[0-9]{2}", safe_text):
                        append_once(tasks / "open.md", f"{line} <!-- status:open {marker} inferred:intent created:{date_text} -->", marker)
                elif category == "decision":
                    append_once(facts / "rules.md", f"{line} <!-- {marker} -->", marker)

            append_line(processed_path, source_hash)

    if not dry_run and legacy_daily_path.exists() and legacy_daily_path != daily_path:
        ensure_file(legacy_daily_path, date_text)
        append_line(legacy_daily_path, f"- [{dt.datetime.now().strftime('%H:%M:%S')}] [memory-curator] Curated {count} inbox item(s), promoted {promoted}.")

    if dry_run:
        print(f"DryRun: would curate {count} item(s). Use --show-items to print memory text.")
    else:
        print(f"Curated {count} item(s), promoted {promoted}.")
    return count, promoted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=str(Path.cwd()))
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-items", action="store_true")
    args = parser.parse_args()
    curate(Path(args.workspace).resolve(), args.date, args.dry_run, args.show_items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

