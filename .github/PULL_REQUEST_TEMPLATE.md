## Summary

Describe the change and why it is needed.

## Testing

- [ ] `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`
- [ ] Install smoke tested with fake credentials or `-NoScheduledTasks`
- [ ] Manual Feishu behavior tested, if applicable

## Safety

- [ ] No app secrets, tokens, open IDs, chat IDs, or generated local config
- [ ] No private chat logs or workspace files
- [ ] No destructive filesystem behavior added

## Compatibility

Note any changes to existing `~/.cc-connect/config.toml` behavior.
