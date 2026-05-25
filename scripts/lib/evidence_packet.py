#!/usr/bin/env python3
"""Build compact evidence packets from codex-feishu workspace records."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

SECRET_PATTERNS = [
    re.compile(r"(?i)[\"']?(api[_-]?key|app[_-]?secret|access[_-]?token|refresh[_-]?token|authorization|password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}\]\)]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]

ID_PATTERNS = [
    re.compile(r"\b(?:ou|oc|om|cli|app|file|img|msg)_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b[A-Fa-f0-9]{24,}\b"),
]

NOISE_RE = re.compile(r"^(?:NO_REPLY|HEARTBEAT_OK|ok|OK|1|/help|/status)\s*$")
JSON_KEY_LINE_RE = re.compile(r'^\s*"[A-Za-z0-9_ -]+"\s*:')

TASK_RE = re.compile(r"负责|需要|帮忙|记得|别忘|提交|完成|整理|测试|汇报|截止|ddl|deadline|todo|待办", re.I)
DECISION_RE = re.compile(r"决定|定了|采用|改成|确认|结论|方案|不再|优先|路线|decision|decided|plan", re.I)
FILE_RE = re.compile(r"上传|文件|附件|归档|INDEX|local_files|\.pdf|\.md|\.docx|\.xlsx|\.png|\.jpg|\.mp4|file", re.I)
RISK_RE = re.compile(r"失败|报错|错误|权限|风险|失效|missing|failed|error|warning|timeout|denied", re.I)
REL_RE = re.compile(r"负责|对接|协作|组长|队长|老师|导师|评审")
TOPIC_RE = re.compile(r"模型|训练|数据集|文档|报告|提交|报名|硬件|传感器|摄像头|原型|飞书|部署|代码|进度|风险")


@dataclass
class EvidenceItem:
    category: str
    time: str
    source: str
    user: str
    text: str
    reason: str
    source_path: str
    line: int = 0


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16].upper()


def redact(text: str) -> tuple[str, int]:
    value = str(text)
    count = 0
    for pattern in SECRET_PATTERNS + ID_PATTERNS:
        matches = pattern.findall(value)
        if matches:
            count += len(matches)
            value = pattern.sub("[REDACTED]", value)
    return value, count


def normalize(text: str, max_chars: int = 240) -> tuple[str, int, bool]:
    value, redactions = redact(text)
    value = re.sub(r"<!--.*?-->", "", value)
    value = re.sub(r"\s+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not value or NOISE_RE.match(value):
        return "", redactions, False
    truncated = False
    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + "..."
        truncated = True
    return value, redactions, truncated


def iter_text_from_obj(obj: Any) -> Iterable[str]:
    if obj is None:
        return
    if isinstance(obj, str):
        stripped = obj.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(obj)
                yield from iter_text_from_obj(parsed)
                return
            except Exception:
                pass
        yield obj
        return
    if isinstance(obj, list):
        for item in obj:
            yield from iter_text_from_obj(item)
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"text", "plain_text", "content", "message", "body", "title", "summary", "description"}:
                yield from iter_text_from_obj(value)
            elif key in {"event", "sender", "data", "message"}:
                yield from iter_text_from_obj(value)


def classify(text: str, source: str) -> tuple[str, str]:
    if FILE_RE.search(text) or source.lower().endswith("index.md"):
        return "文件", "文件或索引信号"
    if RISK_RE.search(text):
        return "风险", "失败/权限/风险信号"
    if TASK_RE.search(text):
        return "任务", "任务或截止信号"
    if DECISION_RE.search(text):
        return "决策", "明确方案或确认"
    if REL_RE.search(text):
        return "关系", "负责人或协作信号"
    if TOPIC_RE.search(text):
        return "话题", "项目主题信号"
    return "最近", "近上下文"


def display_time_from_obj(obj: Any, fallback_mtime: float | None = None) -> str:
    candidates: list[str] = []
    if isinstance(obj, dict):
        for key in ("time", "timestamp", "created_at", "created", "date"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    for value in candidates:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.strftime("%m-%d %H:%M")
        except Exception:
            if re.match(r"^\d{2}:\d{2}", value):
                return value[:5]
            if re.match(r"^\d{4}-\d{2}-\d{2}", value):
                return value[:16].replace("T", " ")
    if fallback_mtime:
        return datetime.fromtimestamp(fallback_mtime).strftime("%m-%d %H:%M")
    return "-- --:--"


def user_from_obj(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    sender = obj.get("sender")
    if isinstance(sender, dict):
        value = sender.get("name") or sender.get("display_name") or sender.get("nickname")
        if isinstance(value, str) and value.strip():
            return value.strip()[:24]
    for key in ("user", "author", "name"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:24]
    return ""


def read_event_items(workspace: Path, max_text_chars: int, recent_limit: int, lookback_hours: int) -> tuple[list[EvidenceItem], dict[str, int]]:
    event_dir = workspace / "memory" / "lark-events"
    stats = {"scanned": 0, "kept": 0, "empty": 0, "truncated": 0, "redacted": 0}
    items: list[EvidenceItem] = []
    if not event_dir.exists():
        return items, stats
    cutoff = datetime.now() - timedelta(hours=lookback_hours)
    files = []
    for path in event_dir.glob("*.ndjson"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) >= cutoff:
                files.append(path)
        except OSError:
            continue
    files = sorted(sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:8], key=lambda p: p.stat().st_mtime)
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-recent_limit:]
        except OSError:
            continue
        for line_no, raw in enumerate(lines, 1):
            if not raw.strip():
                continue
            stats["scanned"] += 1
            try:
                obj = json.loads(raw)
            except Exception:
                stats["empty"] += 1
                continue
            time_text = display_time_from_obj(obj, path.stat().st_mtime)
            user = user_from_obj(obj)
            for candidate in iter_text_from_obj(obj):
                text, redactions, truncated = normalize(candidate, max_text_chars)
                stats["redacted"] += redactions
                if truncated:
                    stats["truncated"] += 1
                if not text:
                    stats["empty"] += 1
                    continue
                category, reason = classify(text, path.name)
                items.append(EvidenceItem(category, time_text, "lark-events", user, text, reason, str(path), line_no))
                stats["kept"] += 1
    return items, stats


def read_private_inbox_items(workspace: Path, date_prefix: str, max_text_chars: int, recent_limit: int) -> tuple[list[EvidenceItem], dict[str, int]]:
    inbox_dir = workspace / "memory" / "inbox"
    stats = {"scanned": 0, "kept": 0, "empty": 0, "truncated": 0, "redacted": 0}
    items: list[EvidenceItem] = []
    if not inbox_dir.exists():
        return items, stats
    files = sorted(inbox_dir.glob(f"{date_prefix}-private-messages*.jsonl"))
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-recent_limit:]
        except OSError:
            continue
        for line_no, raw in enumerate(lines, 1):
            if not raw.strip():
                continue
            stats["scanned"] += 1
            try:
                obj = json.loads(raw)
            except Exception:
                stats["empty"] += 1
                continue
            raw_text = obj.get("text", "") if isinstance(obj, dict) else ""
            if not isinstance(raw_text, str):
                stats["empty"] += 1
                continue
            text, redactions, truncated = normalize(raw_text, max_text_chars)
            stats["redacted"] += redactions
            if truncated:
                stats["truncated"] += 1
            if not text:
                stats["empty"] += 1
                continue
            category = str(obj.get("semantic_category") or obj.get("category") or "") if isinstance(obj, dict) else ""
            kind_map = {
                "preference": ("决策", "私聊偏好或规则"),
                "task": ("任务", "私聊任务请求"),
                "intent": ("任务", "私聊未来意图"),
                "emotion": ("最近", "私聊语气上下文"),
                "relationship": ("关系", "私聊关系线索"),
                "decision": ("决策", "私聊决策"),
                "project": ("话题", "私聊项目线索"),
            }
            display_category, reason = kind_map.get(category, classify(text, path.name))
            items.append(
                EvidenceItem(
                    display_category,
                    display_time_from_obj(obj),
                    "private-inbox",
                    str(obj.get("user") or "")[:24] if isinstance(obj, dict) else "",
                    text,
                    reason,
                    str(path),
                    line_no,
                )
            )
            stats["kept"] += 1
    return items, stats


def read_markdown_items(workspace: Path, rel_paths: list[str], max_text_chars: int, recent_limit: int) -> tuple[list[EvidenceItem], dict[str, int]]:
    stats = {"scanned": 0, "kept": 0, "empty": 0, "truncated": 0, "redacted": 0}
    items: list[EvidenceItem] = []
    for rel in rel_paths:
        path = workspace / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        useful = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
        for line_no, raw in list(enumerate(useful, 1))[-recent_limit:]:
            if JSON_KEY_LINE_RE.match(raw):
                stats["empty"] += 1
                continue
            stats["scanned"] += 1
            text, redactions, truncated = normalize(raw, max_text_chars)
            stats["redacted"] += redactions
            if truncated:
                stats["truncated"] += 1
            if not text:
                stats["empty"] += 1
                continue
            category, reason = classify(text, rel)
            items.append(EvidenceItem(category, "-- --:--", rel.replace("\\", "/"), "", text, reason, str(path), line_no))
            stats["kept"] += 1
    return items, stats


def read_file_metadata_items(workspace: Path, max_text_chars: int, recent_limit: int = 80) -> tuple[list[EvidenceItem], dict[str, int]]:
    metadata_dir = workspace / "local_files" / "metadata"
    stats = {"scanned": 0, "kept": 0, "empty": 0, "truncated": 0, "redacted": 0}
    items: list[EvidenceItem] = []
    if not metadata_dir.exists():
        return items, stats
    files = sorted(metadata_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:recent_limit]
    for path in sorted(files, key=lambda p: p.stat().st_mtime):
        stats["scanned"] += 1
        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
        except Exception:
            stats["empty"] += 1
            continue
        if not isinstance(obj, dict):
            stats["empty"] += 1
            continue
        rel = str(obj.get("path") or "")
        name = str(obj.get("name") or obj.get("original_name") or rel)
        summary = str(obj.get("summary") or "")
        status = str(obj.get("status") or "")
        size = obj.get("size_bytes")
        sha = str(obj.get("sha256") or "")
        size_part = f"; size={size}" if isinstance(size, int) else ""
        sha_part = f"; sha256={sha[:12]}" if sha else ""
        text = f"{name} -> {rel}; status={status}{size_part}{sha_part}; summary={summary}"
        clean, redactions, truncated = normalize(text, max_text_chars)
        stats["redacted"] += redactions
        if truncated:
            stats["truncated"] += 1
        if not clean:
            stats["empty"] += 1
            continue
        items.append(
            EvidenceItem(
                "文件",
                display_time_from_obj(obj, path.stat().st_mtime),
                "file-metadata",
                "-",
                clean,
                "文件元数据",
                str(path),
                1,
            )
        )
        stats["kept"] += 1
    return items, stats


def dedupe_items(items: list[EvidenceItem]) -> tuple[list[EvidenceItem], int]:
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    duplicates = 0
    for item in items:
        key = stable_hash(f"{item.category}:{item.text}")
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(item)
    return unique, duplicates


def limit_items_per_kind(items: list[EvidenceItem], max_items_per_kind: int, include_recent: int) -> tuple[list[EvidenceItem], int]:
    counts: dict[str, int] = {}
    kept: list[EvidenceItem] = []
    dropped = 0
    for item in items:
        limit = include_recent if item.category == "最近" else max_items_per_kind
        count = counts.get(item.category, 0)
        if count >= limit:
            dropped += 1
            continue
        counts[item.category] = count + 1
        kept.append(item)
    return kept, dropped


def build_compact_packet(
    *,
    workspace: Path,
    items: list[EvidenceItem],
    stats: dict[str, int],
    max_chars: int,
    lookback_hours: int,
) -> str:
    rel_workspace = workspace.name
    lines = [
        "字段顺序：类别 | 时间 | 来源 | 用户 | 内容 | 原因",
        f"范围：workspace={rel_workspace}；lookback={lookback_hours}h；扫描={stats.get('scanned', 0)}；保留={len(items)}",
        (
            "丢弃："
            f"空或无效={stats.get('empty', 0)}；"
            f"重复={stats.get('duplicate', 0)}；"
            f"超类别预算={stats.get('over_kind_limit', 0)}；"
            f"超总预算={stats.get('over_char_limit', 0)}；"
            f"截断={stats.get('truncated', 0)}；"
            f"脱敏={stats.get('redacted', 0)}"
        ),
        "",
    ]
    for item in items:
        user = item.user or "-"
        line = f"{item.category} | {item.time} | {item.source} | {user} | {item.text} | {item.reason}"
        if sum(len(x) + 1 for x in lines) + len(line) + 1 > max_chars:
            stats["over_char_limit"] = stats.get("over_char_limit", 0) + 1
            continue
        lines.append(line)
    lines[2] = (
        "丢弃："
        f"空或无效={stats.get('empty', 0)}；"
        f"重复={stats.get('duplicate', 0)}；"
        f"超类别预算={stats.get('over_kind_limit', 0)}；"
        f"超总预算={stats.get('over_char_limit', 0)}；"
        f"截断={stats.get('truncated', 0)}；"
        f"脱敏={stats.get('redacted', 0)}"
    )
    return "\n".join(lines).rstrip() + "\n"


def write_source_map(path: Path, items: list[EvidenceItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            record = {
                "id": stable_hash(f"{item.source_path}:{item.line}:{item.text}"),
                "category": item.category,
                "source_path": item.source_path,
                "line": item.line,
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default

