Codex Feishu group guide

- Normal files/materials: send them to the group. The mini bot can archive them under local_files and update the index.
- Lightweight questions: ask directly. The mini bot may stay silent if the message is casual or not clearly actionable.
- Deep tasks: @ the deep bot. It uses the deep model and can handle longer work directly.
- Continue a task: use Feishu reply on the relevant message to keep the correct session.
- /dream: organize local workspace notes, file index, and durable knowledge.
- /help: show this guide. This is a static command and does not trigger model reasoning.
- /status-index: show deterministic SQLite/FTS index status.
- /health-codex-feishu: run local workspace health checks.
- /workspace-info: show workspace manifest, command surface, and data sources.
- /files find <keyword>: search indexed workspace files.
- /files recent [n]: show recent local files.
- /files pending: show unclassified files under local_files/incoming.
- /knowledge summary: summarize KNOWLEDGE.md.
- /knowledge search <keyword>: search curated workspace knowledge only.
- /memfind <keyword>: search indexed memory and project records.
- /memfind recent [n]: show recent memory records.
- /tasks list: show workspace tasks.
- /task list: show natural-language task-agent records.
- /task preview <text>: parse a natural-language reminder, rota, delete, file, script, or deploy request without executing it.
- /task run <text>: execute low-risk structured task state; missing fields are asked back, high-risk work stops for confirmation. Calendar creation is off unless the local operator enables it.

Planned but not active until confirmation/audit paths exist:

- /remember draft, /remember approve, /forget find, /forget archive, /memory review.
- /files describe, /files ingest pending, /files link, /files archive.

Boundaries:

- Group bots only use this generated workspace.
- They must not read private calendars, email, contacts, private chats, or unrelated computer folders.
- Event hooks and evidence packets redact raw IDs and secrets before they are used as model context.
- /shell, /dir, /cron, /provider, /restart, /upgrade, and /commands are disabled for group projects.
