#!/usr/bin/env python3
"""Build a compact evidence packet for a Feishu group workspace."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.evidence_packet import (  # noqa: E402
    build_compact_packet,
    dedupe_items,
    env_int,
    limit_items_per_kind,
    read_event_items,
    read_file_metadata_items,
    read_markdown_items,
    write_source_map,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Feishu group evidence packet")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output")
    parser.add_argument("--source-map")
    parser.add_argument("--lookback-hours", type=int, default=env_int("CODEX_FEISHU_EVIDENCE_LOOKBACK_HOURS", 72))
    parser.add_argument("--max-chars", type=int, default=env_int("CODEX_FEISHU_EVIDENCE_MAX_CHARS", 12000))
    parser.add_argument("--max-items-per-kind", type=int, default=env_int("CODEX_FEISHU_EVIDENCE_MAX_ITEMS_PER_KIND", 10))
    parser.add_argument("--max-text-chars", type=int, default=env_int("CODEX_FEISHU_EVIDENCE_MAX_TEXT_CHARS", 240))
    parser.add_argument("--recent-limit", type=int, default=120)
    parser.add_argument("--include-recent", type=int, default=12)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise SystemExit(f"workspace missing: {workspace}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(args.output).resolve() if args.output else workspace / "memory" / "evidence" / "group" / f"{stamp}.md"
    source_map = Path(args.source_map).resolve() if args.source_map else output.with_suffix(".source-map.jsonl")

    stats = {"scanned": 0, "kept": 0, "empty": 0, "truncated": 0, "redacted": 0, "duplicate": 0, "over_kind_limit": 0, "over_char_limit": 0}
    event_items, event_stats = read_event_items(workspace, args.max_text_chars, args.recent_limit, args.lookback_hours)
    for key, value in event_stats.items():
        stats[key] = stats.get(key, 0) + value

    rel_paths = [
        "KNOWLEDGE.md",
        "local_files/INDEX.md",
        "memory/tasks/open.md",
        "memory/topics/active.md",
        "memory/people/INDEX.md",
    ]
    today_memory = workspace / "memory" / f"{datetime.now().date().isoformat()}.md"
    if today_memory.exists():
        rel_paths.append(f"memory/{today_memory.name}")
    summary_dir = workspace / "memory" / "summaries"
    if summary_dir.exists():
        for path in sorted(summary_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
            rel_paths.append(str(path.relative_to(workspace)).replace("\\", "/"))

    md_items, md_stats = read_markdown_items(workspace, rel_paths, args.max_text_chars, 80)
    for key, value in md_stats.items():
        stats[key] = stats.get(key, 0) + value
    metadata_items, metadata_stats = read_file_metadata_items(workspace, args.max_text_chars)
    for key, value in metadata_stats.items():
        stats[key] = stats.get(key, 0) + value

    items, duplicates = dedupe_items(event_items + md_items + metadata_items)
    stats["duplicate"] += duplicates
    items, over_kind = limit_items_per_kind(items, args.max_items_per_kind, args.include_recent)
    stats["over_kind_limit"] += over_kind

    packet = build_compact_packet(workspace=workspace, items=items, stats=stats, max_chars=args.max_chars, lookback_hours=args.lookback_hours)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    write_source_map(source_map, items)
    print(f"group_packet={output}")
    print(f"source_map={source_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

