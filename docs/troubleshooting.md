# Troubleshooting

## Normal Messages Do Not Wake the Mini Bot

Check the Feishu mini app first:

- `im.message.receive_v1` is subscribed.
- group all-message permission is approved and published.
- the app version with the permission change is published.
- the mini bot is in the group.

Then check locally:

```powershell
cc-connect sessions list
Get-Content .\cc-connect-run.log -Tail 120
```

You should see `im.message.receive_v1` events for the mini app ID.

## @ Mentions Go to the Wrong Bot

Use two Feishu apps. The deep app should be @-only:

```toml
group_reply_all = false
```

The mini app can monitor all messages:

```toml
group_reply_all = true
```

If both projects share one app, all-message routing can capture @ messages before
the intended deep route.

## Windows Terminal Opens on Every Message

The hook should call the hidden VBS wrapper:

```toml
command = "wscript.exe //B //Nologo \"E:/codex-feishu/scripts/cc-connect-ack-hidden.vbs\""
```

Re-run the installer or update the hook command manually.

## Multiple cc-connect Processes Are Running

Check the process tree:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*cc-connect*' } |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine
```

Stop stale task/process trees and restart the scheduled task:

```powershell
Stop-ScheduledTask -TaskName codex-feishu-cc-connect
Start-ScheduledTask -TaskName codex-feishu-cc-connect
```

## Stream Preview Is Not Visible

Confirm config:

```toml
[stream_preview]
enabled = true
interval_ms = 1000
min_delta_chars = 5
max_chars = 2000
```

Very short replies may finish before a preview update is sent.

## /help or /dream Does Not Work

Check the generated config:

```toml
[[commands]]
name = "help"

[[commands]]
name = "dream"
```

Check the generated workspace:

```powershell
Test-Path .\scripts\help.ps1
Test-Path .\scripts\dream.ps1
Test-Path .\scripts\dream_prompt.md
Test-Path .\local_files\docs\help-guide.md
```

`/dream` also requires the `codex` CLI to be available in the scheduled task
environment.

## Mini Bot Says Acknowledgement Too Often

By default the hook only auto-acknowledges the deep project. The mini project
should send `收到` itself only after it decides a normal group message is worth
handling.

If mini is acknowledging every message, check whether the hook was generated
with `-AckMiniAllMessages` or whether custom instructions are telling mini to
ack casual chat.

## Linux systemd Service Does Not Start

Check service status:

```bash
systemctl --user status codex-feishu-cc-connect.service
journalctl --user -u codex-feishu-cc-connect.service -n 120
```

If `cc-connect` or `codex` is available in your interactive shell but not in the
service, it is usually a PATH issue. Install Node.js/Codex into a system-visible
PATH or run `scripts/start-cc-connect.sh` manually from the same shell profile.
