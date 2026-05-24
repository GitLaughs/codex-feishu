#!/usr/bin/env python3
"""
Lightweight codex-feishu workspace index.

This intentionally stays small: SQLite + FTS5, no daemon, no vector service.
It indexes workspace memory and local files so bot commands can answer common
lookup questions without spending model tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


TEXT_EXTS = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".csv",
    ".ps1",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
}

MAX_TEXT_BYTES = 2_000_000


def workspace_root(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return Path.cwd().resolve()


def db_path(root: Path, value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return root / "memory" / "search" / "codex-feishu-index.sqlite3"


def manifest_workspace(path: Path) -> str | None:
    manifest = path / "workspace_manifest.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return path.name
    workspace = str(data.get("workspace", "")).strip()
    return workspace or path.name


def workspace_base(root: Path, workspace: str) -> Path:
    root_workspace = manifest_workspace(root)
    if workspace in {".", root_workspace}:
        return root
    return root / workspace


def default_workspaces(root: Path) -> list[str]:
    workspaces: list[str] = []
    root_workspace = manifest_workspace(root)
    if root_workspace:
        workspaces.append(root_workspace)
    else:
        workspaces.append(".")
    groups = root / "groups"
    users = root / "users"
    if groups.exists():
        workspaces.extend(
            f"groups/{item.name}"
            for item in sorted(groups.iterdir(), key=lambda p: p.name)
            if item.is_dir()
        )
    if users.exists():
        workspaces.extend(
            f"users/{item.name}"
            for item in sorted(users.iterdir(), key=lambda p: p.name)
            if item.is_dir()
        )
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if not item.is_dir() or item.name.startswith(".") or item.name in {"memory", "runs", "scripts", "docs", "templates"}:
            continue
        name = manifest_workspace(item)
        if name and name not in workspaces:
            workspaces.append(name)
    return workspaces


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_items (
            id TEXT PRIMARY KEY,
            workspace TEXT NOT NULL,
            kind TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            content TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime INTEGER NOT NULL,
            indexed_at INTEGER NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS workspace_items_fts
        USING fts5(id UNINDEXED, workspace, kind, title, summary, content);

        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at INTEGER NOT NULL,
            finished_at INTEGER,
            root TEXT NOT NULL,
            db_path TEXT NOT NULL,
            workspaces_json TEXT NOT NULL,
            indexed_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()


def stable_id(workspace: str, rel_path: str) -> str:
    return hashlib.sha256(f"{workspace}\0{rel_path}".encode("utf-8")).hexdigest()[:24]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> tuple[str, str]:
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    collected = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            if collected < MAX_TEXT_BYTES:
                take = chunk[: MAX_TEXT_BYTES - collected]
                chunks.append(take)
                collected += len(take)
    data = b"".join(chunks)
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc, errors="strict"), digest.hexdigest()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), digest.hexdigest()


def first_meaningful_line(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped:
            return stripped[:160]
    return fallback


def short_summary(text: str, fallback: str) -> str:
    parts = []
    for line in text.splitlines():
        stripped = " ".join(line.strip().split())
        if stripped:
            parts.append(stripped)
        if len(" ".join(parts)) > 300:
            break
    return (" ".join(parts)[:500] or fallback)


def iter_workspace_files(root: Path, workspace: str) -> Iterable[tuple[str, str, Path]]:
    base = workspace_base(root, workspace)
    if base == root:
        bases = [
            ("memory", root / "memory"),
            ("docs", root / "docs"),
            ("local_file", root / "local_files"),
            ("knowledge", root / "KNOWLEDGE.md"),
            ("instructions", root / "INSTRUCTIONS.md"),
            ("manifest", root / "workspace_manifest.json"),
        ]
    else:
        bases = [
            ("memory", base / "memory"),
            ("local_file", base / "local_files"),
            ("knowledge", base / "KNOWLEDGE.md"),
            ("instructions", base / "INSTRUCTIONS.md"),
            ("manifest", base / "workspace_manifest.json"),
        ]

    for kind, base in bases:
        if base.is_file():
            yield kind, base.relative_to(root).as_posix(), base
            continue
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTS:
                continue
            if any(part in {".git", ".cc-connect", "__pycache__"} for part in path.parts):
                continue
            yield kind, path.relative_to(root).as_posix(), path


def upsert_item(
    conn: sqlite3.Connection,
    root: Path,
    workspace: str,
    kind: str,
    rel_path: str,
    path: Path,
) -> None:
    text, digest = read_text(path)
    stat = path.stat()
    title = first_meaningful_line(text, path.name)
    summary = short_summary(text, path.name)
    item_id = stable_id(workspace, rel_path)
    metadata = {
        "ext": path.suffix.lower(),
        "absolute_path": str(path),
    }

    conn.execute(
        """
        INSERT INTO workspace_items (
            id, workspace, kind, rel_path, title, summary, content, sha256,
            size_bytes, mtime, indexed_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            workspace=excluded.workspace,
            kind=excluded.kind,
            rel_path=excluded.rel_path,
            title=excluded.title,
            summary=excluded.summary,
            content=excluded.content,
            sha256=excluded.sha256,
            size_bytes=excluded.size_bytes,
            mtime=excluded.mtime,
            indexed_at=excluded.indexed_at,
            metadata_json=excluded.metadata_json
        """,
        (
            item_id,
            workspace,
            kind,
            rel_path,
            title,
            summary,
            text,
            digest,
            stat.st_size,
            int(stat.st_mtime),
            int(time.time()),
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.execute("DELETE FROM workspace_items_fts WHERE id = ?", (item_id,))
    conn.execute(
        """
        INSERT INTO workspace_items_fts (id, workspace, kind, title, summary, content)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (item_id, workspace, kind, title, summary, text),
    )


def reindex(root: Path, conn: sqlite3.Connection, path: Path, workspaces: list[str]) -> dict:
    init_db(conn)
    started = int(time.time())
    cur = conn.execute(
        "INSERT INTO index_runs (started_at, root, db_path, workspaces_json) VALUES (?, ?, ?, ?)",
        (started, str(root), str(path), json.dumps(workspaces, ensure_ascii=False)),
    )
    run_id = cur.lastrowid
    indexed = 0
    skipped = 0
    seen = set()
    for workspace in workspaces:
        for kind, rel_path, file_path in iter_workspace_files(root, workspace):
            try:
                upsert_item(conn, root, workspace, kind, rel_path, file_path)
                seen.add(stable_id(workspace, rel_path))
                indexed += 1
            except OSError:
                skipped += 1
    for workspace in workspaces:
        existing = conn.execute(
            "SELECT id FROM workspace_items WHERE workspace = ?",
            (workspace,),
        ).fetchall()
        stale = [row["id"] for row in existing if row["id"] not in seen]
        for item_id in stale:
            conn.execute("DELETE FROM workspace_items WHERE id = ?", (item_id,))
            conn.execute("DELETE FROM workspace_items_fts WHERE id = ?", (item_id,))
    conn.execute(
        "UPDATE index_runs SET finished_at = ?, indexed_count = ?, skipped_count = ? WHERE id = ?",
        (int(time.time()), indexed, skipped, run_id),
    )
    conn.commit()
    print(f"indexed={indexed} skipped={skipped} db={path}")
    return {"indexed": indexed, "skipped": skipped, "db": str(path)}


def search(conn: sqlite3.Connection, query: str, workspace: str | None, kinds: list[str] | None, limit: int) -> int:
    init_db(conn)
    where = "workspace_items_fts MATCH ?"
    args: list[object] = [query]
    if workspace:
        where += " AND workspace_items.workspace = ?"
        args.append(workspace)
    if kinds:
        placeholders = ",".join("?" for _ in kinds)
        where += f" AND workspace_items.kind IN ({placeholders})"
        args.extend(kinds)
    args.append(limit)
    try:
        rows = conn.execute(
            f"""
            SELECT workspace_items.id, workspace_items.workspace, workspace_items.kind,
                   workspace_items.title, workspace_items.summary, workspace_items.rel_path,
                   bm25(workspace_items_fts) AS rank
            FROM workspace_items_fts
            JOIN workspace_items USING(id)
            WHERE {where}
            ORDER BY rank
            LIMIT ?
            """,
            args,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        like = f"%{query}%"
        like_where = "(title LIKE ? OR summary LIKE ? OR content LIKE ? OR rel_path LIKE ?)"
        like_args: list[object] = [like, like, like, like]
        if workspace:
            like_where += " AND workspace = ?"
            like_args.append(workspace)
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            like_where += f" AND kind IN ({placeholders})"
            like_args.extend(kinds)
        like_args.append(limit)
        rows = conn.execute(
            f"""
            SELECT id, workspace, kind, title, summary, rel_path
            FROM workspace_items
            WHERE {like_where}
            ORDER BY mtime DESC
            LIMIT ?
            """,
            like_args,
        ).fetchall()
    for row in rows:
        print(
            json.dumps(
                {
                    "workspace": row["workspace"],
                    "kind": row["kind"],
                    "path": row["rel_path"],
                    "title": row["title"],
                    "summary": row["summary"],
                },
                ensure_ascii=False,
            )
        )
    return len(rows)


def runs_dir(root: Path) -> Path:
    path = root / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_run(root: Path, payload: dict) -> None:
    now = time.strftime("%Y-%m-%d", time.localtime())
    path = runs_dir(root) / f"{now}.jsonl"
    payload = dict(payload)
    payload.setdefault("ts", int(time.time()))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def text_fingerprint(text: str) -> dict:
    raw = text.encode("utf-8", errors="replace")
    return {
        "len": len(text),
        "sha256_12": hashlib.sha256(raw).hexdigest()[:12],
    }


def redacted_argv(argv: list[str]) -> list[str]:
    cleaned: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            meta = text_fingerprint(item)
            cleaned.append(f"<query len={meta['len']} sha256_12={meta['sha256_12']}>")
            redact_next = False
            continue
        cleaned.append(item)
        if item == "search":
            redact_next = True
    return cleaned


def status(conn: sqlite3.Connection) -> int:
    init_db(conn)
    totals = conn.execute(
        "SELECT workspace, kind, COUNT(*) AS n FROM workspace_items GROUP BY workspace, kind ORDER BY workspace, kind"
    ).fetchall()
    last = conn.execute(
        "SELECT * FROM index_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    for row in totals:
        print(f"{row['workspace']}\t{row['kind']}\t{row['n']}")
    if last:
        print(
            "last_run="
            + json.dumps(
                {
                    "started_at": last["started_at"],
                    "finished_at": last["finished_at"],
                    "indexed_count": last["indexed_count"],
                    "skipped_count": last["skipped_count"],
                },
                ensure_ascii=False,
            )
        )
    return sum(int(row["n"]) for row in totals)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="codex-feishu memory/file index")
    parser.add_argument("--root", default=None, help="CODEX_FEISHU root; defaults to cwd")
    parser.add_argument("--db", default=None, help="SQLite db path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reindex = sub.add_parser("reindex", help="rebuild index")
    p_reindex.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        help="workspace to index; repeatable. default: main memory plus known group workspaces",
    )

    p_search = sub.add_parser("search", help="search index")
    p_search.add_argument("query")
    p_search.add_argument("--workspace", default=None)
    p_search.add_argument("--kind", action="append", dest="kinds", default=None)
    p_search.add_argument("--limit", type=int, default=8)

    sub.add_parser("status", help="show index status")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = workspace_root(args.root)
    path = db_path(root, args.db)
    conn = connect(path)
    started = time.time()
    run_payload = {
        "tool": "codex-feishu-index",
        "cmd": args.cmd,
        "argv": redacted_argv(argv),
        "root": str(root),
        "db": str(path),
    }
    try:
        if args.cmd == "reindex":
            workspaces = args.workspaces or default_workspaces(root)
            result = reindex(root, conn, path, workspaces)
            run_payload.update({"workspaces": workspaces, "result": result})
        elif args.cmd == "search":
            result_count = search(conn, args.query, args.workspace, args.kinds, args.limit)
            run_payload.update(
                {
                    "query": text_fingerprint(args.query),
                    "workspace": args.workspace,
                    "kinds": args.kinds,
                    "limit": args.limit,
                    "result_count": result_count,
                }
            )
        elif args.cmd == "status":
            item_count = status(conn)
            run_payload.update({"item_count": item_count})
        run_payload.update({"ok": True, "duration_ms": int((time.time() - started) * 1000)})
        append_run(root, run_payload)
        return 0
    except Exception as exc:
        run_payload.update(
            {
                "ok": False,
                "duration_ms": int((time.time() - started) * 1000),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        append_run(root, run_payload)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
