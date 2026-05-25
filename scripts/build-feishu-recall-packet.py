#!/usr/bin/env python3
"""Build compact recall output from codex-feishu memory index or curated files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.evidence_packet import normalize, redact, stable_hash  # noqa: E402


def score_text(text: str, path: str, tokens: list[str]) -> int:
    score = 0
    lower_text = text.lower()
    lower_path = path.lower()
    for token in tokens:
        value = token.lower()
        if value in lower_text:
            score += 3
        if value in lower_path:
            score += 1
    match = re.search(r"\[(preference|task|decision|intent|emotion|project|people|relationship|note)/([0-9])\]", text)
    if match:
        score += int(match.group(2))
    return score


def iter_index_records(workspace: Path) -> list[dict[str, object]]:
    index_path = workspace / "memory" / "search" / "index.jsonl"
    records: list[dict[str, object]] = []
    if index_path.exists():
        for raw in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                records.append(item)
        return records

    roots = [
        workspace / "memory" / "daily",
        workspace / "memory" / "facts",
        workspace / "memory" / "projects",
        workspace / "memory" / "tasks",
        workspace / "memory" / "people",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, 1):
                if line.strip():
                    records.append({"path": str(path.relative_to(workspace)), "line": line_no, "text": line, "kind": "memory_line"})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact recall packet")
    parser.add_argument("--workspace", default=str(Path.cwd()))
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--max-text-chars", type=int, default=260)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    tokens = [item for item in re.split(r"\s+", args.query.strip()) if item]
    scored = []
    for record in iter_index_records(workspace):
        text = str(record.get("text") or "")
        path = str(record.get("path") or record.get("source") or "")
        score = score_text(text, path, tokens)
        if score <= 0:
            continue
        clean, redactions, truncated = normalize(text, args.max_text_chars)
        clean, extra_redactions = redact(clean)
        redactions += extra_redactions
        if not clean:
            continue
        scored.append(
            {
                "score": score,
                "path": path,
                "line": int(record.get("line") or 0),
                "text": clean,
                "redactions": redactions,
                "truncated": truncated,
                "id": stable_hash(f"{path}:{record.get('line')}:{clean}"),
            }
        )
    scored.sort(key=lambda item: (-int(item["score"]), str(item["path"]), int(item["line"])))
    kept = scored[: args.limit]
    print("字段顺序：分数 | 来源 | 行 | 内容")
    print(f"范围：workspace={workspace.name}；query={args.query}；扫描={len(scored)}；保留={len(kept)}")
    dropped = max(0, len(scored) - len(kept))
    print(f"丢弃：超结果上限={dropped}；脱敏={sum(int(item['redactions']) for item in kept)}；截断={sum(1 for item in kept if item['truncated'])}")
    print("")
    for item in kept:
        print(f"{item['score']} | {item['path']} | {item['line']} | {item['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

