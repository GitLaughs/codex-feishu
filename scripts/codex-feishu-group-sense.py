#!/usr/bin/env python3
"""Extract lightweight group tasks, topics, and role hints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

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

DEFAULT_TOPICS = [
    "模型",
    "训练",
    "数据集",
    "文档",
    "报告",
    "提交",
    "报名",
    "硬件",
    "传感器",
    "摄像头",
    "原型",
    "飞书",
    "部署",
    "代码",
    "进度",
    "风险",
]

DUE_RE = re.compile(
    r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}[月/][0-9]{1,2}[日号]?|"
    r"今天|明天|后天|本周|这周|下周|周[一二三四五六日天][前晚]?|月底|赛前|答辩前|提交前"
)
TASK_RE = re.compile(r"负责|需要|帮忙|记得|别忘|提交|完成|整理|测试|汇报|截止|ddl|deadline|todo|待办", re.I)
REL_RE = re.compile(r"(?P<name>[\u4e00-\u9fffA-Za-z0-9_]{1,16}).{0,4}(负责|对接|协作|组长|队长|老师|导师|评审)(?P<area>[^，。,.!?！？\r\n]{0,40})")
ASSIGN_RE = re.compile(r"(?:让|请|麻烦|安排)\s*[@＠]?(?P<name>[\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:去|来)?(?P<action>测试|测一下|整理|确认|提交|看看|看一下|对接|修|写|改)(?P<area>[^，。,.!?！？\r\n]{0,40})", re.I)
REVIEW_RE = re.compile(r"(?:[@＠](?P<name_at>[\u4e00-\u9fffA-Za-z0-9_]{1,16})|(?P<name>[\u4e00-\u9fffA-Za-z0-9_]{1,16})[，,\s:：]+)(?:这个|这块|这里|方案|文档|报告|数据|模型|传感器方案)?.{0,8}(?P<action>看看|看一下|确认|评审|review|测试|测一下)", re.I)
HISTORY_RE = re.compile(r"(?P<name>[\u4e00-\u9fffA-Za-z0-9_]{1,16})上次(?:说|提|给|发)的(?P<area>方案|文档|报告|建议|数据|模型)")
AUTHORITY_RE = re.compile(r"(?:听|按)\s*[@＠]?(?P<name>[\u4e00-\u9fffA-Za-z0-9_]{1,16})(?:的|说的|方案|安排)|[@＠]?(?P<name2>[\u4e00-\u9fffA-Za-z0-9_]{1,16})说了算")
RELATION_CONTEXT_RE = re.compile(r"文档|报告|方案|模型|训练|数据|硬件|传感器|摄像头|原型|飞书|部署|代码|进度|风险|测试|提交|答辩|评审|对接|负责|整理|确认")
CASUAL_RELATION_RE = re.compile(r"吃饭|吃啥|今晚|聚餐|外卖|电影|来不来")
NAME_STOPWORDS = {
    "今天",
    "明天",
    "后天",
    "这个",
    "这块",
    "这里",
    "大家",
    "我们",
    "你们",
    "他们",
    "她们",
    "群里",
    "有人",
}


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def normalize(value: str) -> str:
    text = re.sub(r"\s+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not text or text in {"NO_REPLY", "HEARTBEAT_OK"} or text.startswith("/help"):
        return ""
    if len(text) > 800:
        text = text[:800] + "..."
    return redact(text)


def ensure_file(path: Path, title: str, dry_run: bool) -> None:
    if dry_run or path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n", encoding="utf-8")


def add_unique_line(path: Path, title: str, line: str, marker: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"dry_run add {path} {line}")
        return True
    ensure_file(path, title, dry_run=False)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker.lower() in existing.lower():
        return False
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return True


def text_from_obj(obj: Any) -> Iterable[str]:
    if obj is None:
        return
    if isinstance(obj, str):
        stripped = obj.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(obj)
                yield from text_from_obj(parsed)
                return
            except Exception:
                yield obj
                return
        yield obj
        return
    if isinstance(obj, list):
        for item in obj:
            yield from text_from_obj(item)
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"text", "plain_text", "content", "message", "body", "title", "summary"}:
                yield from text_from_obj(value)
            elif key in {"event", "sender", "data"}:
                yield from text_from_obj(value)


def read_messages(workspace: Path, date: str, inline_text: list[str], limit: int) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in inline_text:
        text = normalize(item)
        if text:
            messages.append({"source": "inline", "text": text})

    event_dir = workspace / "memory" / "lark-events"
    if event_dir.exists():
        files = sorted(
            sorted(event_dir.glob("*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)[:8],
            key=lambda p: p.stat().st_mtime,
        )
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
            except OSError:
                continue
            for raw in lines:
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                for candidate in text_from_obj(obj):
                    text = normalize(candidate)
                    if text:
                        messages.append({"source": path.name, "text": text})

    daily_path = workspace / "memory" / f"{date}.md"
    if daily_path.exists():
        for raw in daily_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
            text = normalize(raw)
            if text and not text.startswith("#"):
                messages.append({"source": daily_path.name, "text": text})

    return messages[-limit:]


def build_group_packet(workspace: Path, dry_run: bool) -> list[str]:
    if dry_run:
        return []
    script = Path(__file__).with_name("build-feishu-group-packet.py")
    if not script.exists():
        return [f"evidence_packet=error script={script.name} reason=missing"]
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--workspace", str(workspace)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return [f"evidence_packet=error script={script.name} reason=timeout"]
    except OSError as exc:
        return [f"evidence_packet=error script={script.name} reason={normalize(str(exc))[:120]}"]
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0:
        detail = normalize(proc.stderr or proc.stdout)[:120]
        return [f"evidence_packet=error script={script.name} exit={proc.returncode} detail={detail}"]
    return [f"evidence_packet=detail {line}" for line in lines]


def load_topics(workspace: Path) -> list[str]:
    manifest = workspace / "workspace_manifest.json"
    if not manifest.exists():
        return DEFAULT_TOPICS
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:
        return DEFAULT_TOPICS
    raw_topics = data.get("topics") if isinstance(data, dict) else None
    if not isinstance(raw_topics, list):
        return DEFAULT_TOPICS
    topics: list[str] = []
    seen: set[str] = set()
    for item in raw_topics:
        if not isinstance(item, str):
            continue
        topic = item.strip()
        key = topic.lower()
        if not topic or key in seen:
            continue
        seen.add(key)
        topics.append(topic)
    return topics or DEFAULT_TOPICS


def topic_label(text: str, topics: list[str]) -> str:
    lowered = text.lower()
    for topic in topics:
        if topic.lower() in lowered:
            return topic
    return ""


def clean_name(value: str) -> str:
    return value.strip().lstrip("@＠").strip()


def valid_name(value: str) -> bool:
    name = clean_name(value)
    if not name or name in NAME_STOPWORDS:
        return False
    if name.startswith("[REDACTED]"):
        return False
    return True


def likely_private_chatter(text: str) -> bool:
    return bool(CASUAL_RELATION_RE.search(text) and not RELATION_CONTEXT_RE.search(text))


def relationship_fact(text: str) -> tuple[str, str, str] | None:
    if likely_private_chatter(text):
        return None

    match = REL_RE.search(text)
    if match and valid_name(match.group("name")):
        area = match.group("area").strip() or match.group(2)
        if match.group(2) in {"老师", "导师", "评审"} and not RELATION_CONTEXT_RE.search(area):
            return None
        return clean_name(match.group("name")), "explicit_role", area

    match = ASSIGN_RE.search(text)
    if match and valid_name(match.group("name")):
        area = f"{match.group('action')}{match.group('area').strip()}"
        return clean_name(match.group("name")), "assignment", area

    match = REVIEW_RE.search(text)
    if match:
        name = match.group("name_at") or match.group("name") or ""
        if valid_name(name):
            return clean_name(name), "review_request", match.group("action")

    match = HISTORY_RE.search(text)
    if match and valid_name(match.group("name")):
        area = match.group("area") or "历史方案"
        return clean_name(match.group("name")), "history_reference", area

    match = AUTHORITY_RE.search(text)
    if match:
        name = match.group("name") or match.group("name2") or ""
        if valid_name(name):
            return clean_name(name), "authority", "决策参考"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--recent-limit", type=int, default=120)
    parser.add_argument("--min-summary-messages", type=int, default=12)
    parser.add_argument("--text", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    memory = workspace / "memory"
    tasks_path = memory / "tasks" / "open.md"
    people_path = memory / "people" / "INDEX.md"
    topics_path = memory / "topics" / "active.md"
    summary_path = memory / "summaries" / f"{args.date}.md"
    for path, title in [
        (tasks_path, "Open Group Tasks"),
        (people_path, "Group People"),
        (topics_path, "Active Topics"),
        (summary_path, f"{args.date} Group Sense"),
    ]:
        ensure_file(path, title, args.dry_run)

    messages = read_messages(workspace, args.date, args.text, args.recent_limit)
    topics = load_topics(workspace)
    now = datetime.now().strftime("%H:%M:%S")
    created = args.date
    task_count = people_count = topic_count = 0
    reminders: list[str] = []

    for msg in messages:
        text = msg["text"]
        marker = f"source:{stable_hash(msg['source'] + ':' + text)}"
        due_match = DUE_RE.search(text)
        due = due_match.group(0) if due_match else ""

        if TASK_RE.search(text):
            due_part = f" due:{due}" if due else ""
            line = f"- [{now}] [task/4] [group-sense] {text} <!-- status:open {marker} created:{created}{due_part} -->"
            if add_unique_line(tasks_path, "Open Group Tasks", line, marker, args.dry_run):
                task_count += 1
            if due:
                reminders.append(f"reminder_candidate workspace={workspace} due={due} hash={stable_hash(marker)}")

        rel = relationship_fact(text)
        if rel:
            name, kind, area = rel
            line = f"- [{now}] [relationship/4] [group-sense] {name} -> {area}; relation:{kind}; evidence: {text} <!-- {marker} -->"
            if add_unique_line(people_path, "Group People", line, marker, args.dry_run):
                people_count += 1

        topic = topic_label(text, topics)
        if topic:
            line = f"- [{now}] [topic/3] [group-sense] {topic}: {text} <!-- {marker} -->"
            if add_unique_line(topics_path, "Active Topics", line, marker, args.dry_run):
                topic_count += 1

    if len(messages) >= args.min_summary_messages:
        topic_counts: dict[str, int] = {}
        for msg in messages:
            topic = topic_label(msg["text"], topics)
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        topic_text = ", ".join(f"{k}({v})" for k, v in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:5])
        marker = f"source:{stable_hash(f'summary:{args.date}:{len(messages)}:{topic_text}')}"
        line = f"- [{now}] [summary/3] [group-sense] recent_messages={len(messages)}; topics={topic_text}; tasks_added={task_count}; relationships_added={people_count} <!-- {marker} -->"
        add_unique_line(summary_path, f"{args.date} Group Sense", line, marker, args.dry_run)

    packet_lines = build_group_packet(workspace, args.dry_run)
    print(
        f"group_sense=ok workspace={workspace} messages={len(messages)} "
        f"tasks_added={task_count} people_added={people_count} topics_added={topic_count}"
    )
    for line in packet_lines:
        print(line)
    for item in sorted(set(reminders)):
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

