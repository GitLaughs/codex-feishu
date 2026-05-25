#!/usr/bin/env python3
"""Capture cc-connect private messages into codex-feishu inbox memory."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PRIVATE_PROJECTS: set[str] = set()

SECRET_PATTERNS = [
    re.compile(r"(?i)[\"']?(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}\]\)]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]

TRIGGERS: dict[str, list[str]] = {
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

NOISE_PATTERNS = [
    re.compile(r"^(ok|OK|1|hhhh|hh|test)$"),
    re.compile(r"^/[\w\-]+(\s*)$"),
]

DEFAULT_MAX_JSONL_BYTES = 5 * 1024 * 1024


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> tuple[str, bool]:
    value = str(text)
    redacted = False
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            redacted = True
            value = pattern.sub("[REDACTED]", value)
    return value, redacted


def env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def trigger_match(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term and term.lower() in lowered for term in terms)


def category_for(text: str) -> str:
    for category in ("preference", "emotion", "relationship", "intent", "task", "decision", "project", "people"):
        if trigger_match(text, TRIGGERS.get(category, [])):
            return category
    if re.search(r"(?i)\b(i feel|i am feeling|felt)\b|我(有点|很|真的)?(累|烦|慌|怕|开心|难受|焦虑|紧张)", text):
        return "emotion"
    if re.search(r"(我|我们).{0,8}(想|打算|准备|计划|可能要|预计|希望|考虑)", text):
        return "intent"
    if re.search(r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}).{0,6}(负责|对接|协作|组长|队长|老师|导师)", text):
        return "relationship"
    return "note"


def importance_for(category: str, text: str) -> int:
    score = 1
    if category in {"preference", "task", "decision"}:
        score += 2
    if category in {"emotion", "intent", "relationship"}:
        score += 2
    if category in {"project", "people"}:
        score += 1
    if trigger_match(text, TRIGGERS["important"]):
        score += 2
    if len(text) > 80:
        score += 1
    if category == "emotion" and re.search(r"连续|一直|又|最近|今天|今晚|这几天|睡不着|来不及|崩溃", text):
        score += 1
    if category == "intent" and re.search(r"今天|明天|后天|下周|周末|[0-9]{1,2}[月/][0-9]{1,2}|[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        score += 1
    return min(score, 5)


def ensure_file(path: Path, title: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {title}\n\n", encoding="utf-8")


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def max_jsonl_bytes() -> int:
    raw = os.environ.get("CODEX_FEISHU_PRIVATE_INBOX_MAX_BYTES", "")
    if not raw:
        return DEFAULT_MAX_JSONL_BYTES
    try:
        return max(1024, int(raw))
    except ValueError:
        return DEFAULT_MAX_JSONL_BYTES


def rotating_jsonl_path(directory: Path, stem: str, suffix: str, next_line: str, max_bytes: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"{stem}{suffix}"
    candidates = [base] + sorted(directory.glob(f"{stem}-[0-9][0-9][0-9]{suffix}"))
    encoded_len = len((next_line + "\n").encode("utf-8"))
    for path in candidates:
        if not path.exists():
            return path
        try:
            if path.stat().st_size + encoded_len <= max_bytes:
                return path
        except OSError:
            continue
    return directory / f"{stem}-{len(candidates):03d}{suffix}"


def memory_line(time_text: str, category: str, importance: int, source: str, text: str) -> str:
    return f"- [{time_text}] [{category}/{importance}] [{source}] {text}"


def timestamp_parts(timestamp: str) -> tuple[str, str]:
    if timestamp:
        try:
            parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return parsed.date().isoformat(), parsed.strftime("%H:%M:%S")
        except Exception:
            pass
    now = dt.datetime.now().astimezone()
    return now.date().isoformat(), now.strftime("%H:%M:%S")


def capture() -> tuple[bool, str]:
    if os.environ.get("CC_HOOK_EVENT", "") not in {"", "message.received"}:
        return False, "ignored_event"

    project = os.environ.get("CC_HOOK_PROJECT", "")
    allowed = {
        item.strip()
        for item in os.environ.get("CODEX_FEISHU_PRIVATE_CAPTURE_PROJECTS", "").split(",")
        if item.strip()
    } or PRIVATE_PROJECTS
    if allowed and project and project not in allowed:
        return False, "ignored_project"

    text = env_first("CC_HOOK_TEXT", "CC_HOOK_CONTENT", "CC_HOOK_MESSAGE", "CC_HOOK_MESSAGE_TEXT").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return False, "empty_text"
    if len(text) < 8 and not any(trigger_match(text, terms) for terms in TRIGGERS.values()):
        return False, "short_noise"
    if any(pattern.match(text) for pattern in NOISE_PATTERNS):
        return False, "noise"

    safe_text, was_redacted = redact(text)
    if len(safe_text) > 500:
        safe_text = safe_text[:500] + "..."

    root = Path(os.environ.get("CODEX_FEISHU_ROOT", os.environ.get("CODEX_FEISHU_WORKSPACE", "/opt/codex-feishu"))).resolve()
    memory = root / "memory"
    inbox = memory / "inbox"
    daily = memory / "daily"
    date_text, time_text = timestamp_parts(os.environ.get("CC_HOOK_TIMESTAMP", ""))
    semantic_category = category_for(safe_text)
    importance = importance_for(semantic_category, safe_text)
    category = semantic_category if importance >= 3 else "candidate"

    entry = {
        "time": time_text,
        "project": project,
        "session_hash": stable_hash(os.environ.get("CC_HOOK_SESSION_KEY", "")) if os.environ.get("CC_HOOK_SESSION_KEY") else "",
        "user": env_first("CC_HOOK_USER_NAME", "CC_HOOK_SENDER_NAME", "CC_HOOK_NAME"),
        "user_id_hash": stable_hash(env_first("CC_HOOK_USER_ID", "CC_HOOK_SENDER_ID", "CC_HOOK_OPEN_ID", "CC_HOOK_USER_OPEN_ID")) if env_first("CC_HOOK_USER_ID", "CC_HOOK_SENDER_ID", "CC_HOOK_OPEN_ID", "CC_HOOK_USER_OPEN_ID") else "",
        "category": category,
        "semantic_category": semantic_category,
        "importance": importance,
        "redacted": was_redacted,
        "text": safe_text,
    }
    entry_line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    inbox_path = rotating_jsonl_path(
        inbox,
        f"{date_text}-private-messages",
        ".jsonl",
        entry_line,
        max_jsonl_bytes(),
    )
    append_line(inbox_path, entry_line)

    if category != "candidate":
        line = memory_line(time_text, semantic_category, importance, "hook", safe_text)
        if was_redacted:
            line += " (redacted)"
        legacy_daily = memory / f"{date_text}.md"
        layered_daily = daily / f"{date_text}.md"
        ensure_file(legacy_daily, date_text)
        ensure_file(layered_daily, f"{date_text} Daily")
        append_line(legacy_daily, line)
        append_line(layered_daily, line)

    return True, str(inbox_path)


def main() -> int:
    ok, detail = capture()
    if os.environ.get("CODEX_FEISHU_PRIVATE_CAPTURE_VERBOSE") == "1":
        print(json.dumps({"ok": ok, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

