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
        H[optional memory hook]
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
- Optional patched-runtime guard uses `ignore_bot_mentions` to drop deep bot @
  messages and later same-topic replies before the mini agent starts.
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
- Patched runtimes can send a platform-layer acknowledgement with
  `instant_ack_text`, before the model begins long work.

## Immediate Acknowledgement

Immediate “received” messages are a Feishu platform option, not a default
`message.received` command hook:

```toml
instant_ack_text = "收到正在输出，请等等我。"
```

This keeps acknowledgement delivery in the route that already knows which bot
and message are being handled. The legacy `cc-connect-ack.*` scripts remain in
the repository for older deployments, but the generated double-bot templates do
not use them by default.

## Mention/Topic Guard

In all-message mode, Feishu can deliver a root `@deep-bot` message to the mini
app as a normal group event. A runtime that supports `ignore_bot_mentions` lets
the mini platform discard those events before model routing:

```toml
ignore_bot_mentions = ["feishu-deep", "ou_deep_bot_open_id"]
```

The guard also remembers the root Feishu topic/reply chain, so follow-up replies
under the deep task stay with the deep project instead of waking mini.

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

The Windows install script registers:

- a hidden runner task that starts `cc-connect`;
- a hidden watchdog task that restarts the runner if `cc-connect.exe` is gone.

The default configuration does not need an acknowledgement hook, so incoming
messages do not spawn a hidden ack process.

The Linux install script writes the same project/workspace config and can create
a systemd user service:

```text
~/.config/systemd/user/codex-feishu-cc-connect.service
```

Linux hooks use `bash` scripts instead of VBS/PowerShell wrappers.

## Optional Family Memory Hook

When enabled, the installer adds a single `message.received` hook for local
memory capture:

```toml
[[hooks]]
event = "message.received"
type = "command"
command = "... cc-connect-memory-hook ..."
async = true
timeout = 8
```

The hook is intentionally narrow. It filters by project, ignores non-message
events, and records explicit memory/task/shopping-list messages under the
workspace `memory` folder. It does not send acknowledgements.

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
