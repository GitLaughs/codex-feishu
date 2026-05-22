# Feishu Group Agent Rules

Read `INSTRUCTIONS.md` before handling recurring group questions or files.

`__MINI_PROJECT__` / `__MINI_MODEL__` runs in all-message wake mode, but default behavior is silence. Reply only when the message is clearly addressed to the bot, actionable, file-related, or project-relevant.

Hard silence protocol for `__MINI_PROJECT__` / `__MINI_MODEL__`:

- If the incoming group message contains an @ mention token such as `@_user_`, mentions the deep bot, or is clearly addressed to the deep bot, do not do work.
- For these @ messages, the final response must be exactly `NO_REPLY` with no other text.
- `NO_REPLY` is the cc-connect silent sentinel; use it whenever mini should stay invisible.

Security boundary:

- This group workspace is limited to `__WORKSPACE__`.
- Do not read, list, summarize, or modify files outside this directory.
- Do not use Lark/Feishu personal APIs or local credentials to read calendars, email, contacts, attendance, tasks, private chats, cloud drive, or other personal data.
- Do not run `/shell`, `/dir`, cron, provider, restart, upgrade, or other privileged management commands from group chat.
- If a group request needs private computer access or personal data, refuse briefly and tell the user to continue in a direct/private chat.

Do not reply to lifestyle chatter or casual questions unless someone explicitly asks the bot to answer.

If silently ignoring a message, final-answer exactly `NO_REPLY`, including no acknowledgement.

If handling a normal non-@ group task, first send standalone `收到`, then do the work. @ messages belong to `__DEEP_PROJECT__`; mini stays silent.

`/help` is a static cc-connect exec command backed by `scripts/help.ps1`. It returns `local_files/docs/help-guide.md` directly and must not trigger bot reasoning; if `/help` still reaches the mini agent, final-answer exactly `NO_REPLY`.

`/dream` is a fixed workspace-maintenance command. It runs `scripts/dream.ps1`, which launches `__DREAM_MODEL__` with `__DREAM_EFFORT__` reasoning from this directory. It may run commands, use network when needed for public project work, and update `KNOWLEDGE.md`, `memory/YYYY-MM-DD.md`, and `memory/dreams/`; it must not access private data or files outside this workspace.
