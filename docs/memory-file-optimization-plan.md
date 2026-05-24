# Memory and File Management Roadmap

This roadmap turns the current workspace files and local memory folders into a deterministic, auditable Feishu group knowledge layer.

## Current Release Surface

The package now generates:

- `workspace_manifest.json` for each generated group workspace.
- Read-only deterministic commands:
  - `/files find <keyword>`
  - `/files recent [n]`
  - `/files pending`
  - `/knowledge summary`
  - `/knowledge search <keyword>`
  - `/memfind <keyword>`
  - `/memfind recent [n]`
  - `/tasks list`
  - `/workspace-info`
  - `/status-index`
  - `/health-codex-feishu`
- SQLite/FTS5 local indexing through `scripts/codex-feishu-index.py`.
- Health checks for manifest, help guide, file index, memory files, and redacted run logs.

These commands are intentionally read-only. They reduce model calls for common lookup work without letting group chat mutate durable memory by accident.

## Planned Write Path

Write commands stay in `planned_commands` until confirmation and audit flows exist:

- `/remember draft <text>` creates a candidate memory item.
- `/remember approve <id>` promotes a candidate to curated memory.
- `/forget find <query>` lists candidates for archival.
- `/forget archive <id>` performs soft delete with audit history.
- `/memory review` shows stale, duplicate, candidate, and low-confidence items.

Every write path should record:

- workspace
- source path or redacted source event
- created/updated time
- confidence
- privacy scope
- active/archived/deleted status

## File Pipeline

The target file lifecycle is:

```text
incoming -> classify -> metadata -> INDEX.md -> SQLite/FTS -> linked task or memory
```

Recommended metadata fields:

- path
- sha256
- original name
- MIME/type
- source
- received time
- summary
- status
- linked memory/task IDs

## Safety Rules

- Group workspaces must not read private mail, calendar, contacts, credentials, or unrelated folders.
- Runs logs must store query fingerprints, not raw search text.
- Active commands must not include planned write commands.
- Deletion must be soft-delete until a separate retention policy exists.
- `/health-codex-feishu` should stay green before publishing a workspace update.
