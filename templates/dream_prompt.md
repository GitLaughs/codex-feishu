You are running `/dream` for the Feishu group workspace `__WORKSPACE__`.

Purpose: run a deliberate memory-maintenance pass: orient, gather, consolidate, prune, and report.

Hard boundaries:

- Only read, write, list, or summarize files under `__WORKSPACE__`.
- Do not follow junctions, symlinks, or reparse points.
- Do not read calendars, email, contacts, tasks, private chats, cloud drive, credentials, global memory, or files outside this workspace.
- Do not use Lark/Feishu personal APIs.
- Use network only when it directly helps workspace organization, such as fetching a referenced public repository.
- Do not edit `AGENTS.md` or `INSTRUCTIONS.md` unless a contradiction makes the dream impossible; if so, report instead of editing.

Workflow:

1. Orient
   - Read `AGENTS.md`, `INSTRUCTIONS.md`, `KNOWLEDGE.md`, `local_files/INDEX.md`, and recent `memory/*.md` files if present.
   - Build a short map of what the workspace currently knows.

2. Gather
   - Inspect the local file tree under `local_files/` by names, paths, sizes, and obvious text summaries.
   - For large files, do not deeply parse content unless an existing index points to a missing summary.
   - Check whether `INDEX.md`, `KNOWLEDGE.md`, and `memory/YYYY-MM-DD.md` disagree.

3. Consolidate
   - Add durable facts, decisions, and useful project state into `KNOWLEDGE.md`.
   - Add raw notes or a dream log into `memory/YYYY-MM-DD.md`.
   - If helpful, create a detailed report under `memory/dreams/YYYY-MM-DD-HHMMSS.md`.
   - Keep updates concise. Do not duplicate facts already stated well.

4. Prune
   - Mark stale or superseded notes only when there is clear evidence.
   - Do not delete original files.
   - Do not remove user-authored project material.

5. Report
   - Final reply must be short and suitable for group chat.
   - Include changed file paths and the 3-6 most useful findings/actions.
   - If no useful changes were needed, say so and explain what was checked.
