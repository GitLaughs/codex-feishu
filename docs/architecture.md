# Architecture

`codex-feishu` uses two Feishu apps because a single bot cannot reliably be both
an all-message monitor and a clean @-only deep worker.

## Components

```mermaid
flowchart TB
    subgraph Feishu
        G[Group chat]
        M[Mini bot app]
        D[Deep bot app]
    end

    subgraph Local Windows Host
        C[cc-connect]
        H[message.received hook]
        CMD[/help + /dream commands]
        W[workspace]
        S[scheduled task + watchdog]
    end

    subgraph Codex
        AM[Mini project]
        AD[Deep project]
    end

    G --> M --> C --> AM
    G --> D --> C --> AD
    C --> H
    C --> CMD
    AM --> W
    AD --> W
    CMD --> W
    S --> C
```

## Routing

Mini project:

- Feishu app has group all-message permission.
- cc-connect uses `group_reply_all = true`.
- The `gpt-5.4-mini` project decides whether a reply is useful.
- A configurable mini reply trigger threshold controls how conservative this
  decision should be: `relaxed`, `medium`, or `strict`.
- Files and useful context can be processed without an @ mention.

The default threshold is `strict`. In that mode, casual chat and standalone
question marks do not trigger replies; explicit bot-directed work, actionable
tasks, file handling, or important project context can trigger replies.

Deep project:

- Feishu app is invited to the group.
- cc-connect uses `group_reply_all = false`.
- Only @ mentions wake the deep model.
- Complex work stays in the deep bot's own thread/session.

## Session Isolation

Both projects use:

```toml
thread_isolation = true
reply_to_trigger = true
```

This maps Feishu reply chains to separate agent sessions. Two users can ask
different root @ questions at the same time, then continue the correct task by
using Feishu reply under the relevant message.

## Background Execution

The install script registers:

- a hidden runner task that starts `cc-connect`;
- a hidden watchdog task that restarts the runner if `cc-connect.exe` is gone.

The acknowledgement hook uses a VBS wrapper and `wscript.exe` so Windows Terminal
does not open for every incoming message.

## Static Commands

The generated config includes:

```toml
[[commands]]
name = "help"

[[commands]]
name = "dream"
```

`/help` returns a static guide from `local_files/docs/help-guide.md`.
`/dream` runs a workspace maintenance pass from the group workspace, using the
configured deep model and writing detailed notes under `memory`.

Both group projects disable privileged cc-connect management commands such as
`/shell`, `/dir`, `/cron`, `/provider`, `/restart`, `/upgrade`, and `/commands`.
