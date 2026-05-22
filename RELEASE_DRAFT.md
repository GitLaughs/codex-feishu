# codex-feishu v0.3.0

Adds optional Codex API balance rotation for Linux deployments that use cc-switch opentoken providers.

## Highlights

- New `scripts/codex-balance-rotate.py` checks cc-switch Codex providers, queries `/v1/usage`, and selects the provider with the highest positive remaining balance.
- Linux installer can now register a systemd user timer with `--enable-codex-balance-rotate`.
- The timer defaults to every 30 minutes and writes the selected key to Codex auth for future sessions.
- The rotation is intentionally not an in-flight retry layer. If a chat request fails because an API is exhausted or temporarily unavailable, users should resend after the key has switched.

## Install

Linux balance rotation example:

```bash
bash ./scripts/install-linux.sh \
  --enable-codex-balance-rotate \
  --codex-rotate-db-path "$HOME/.cc-switch/cc-switch.db" \
  --codex-rotate-auth-path "$HOME/.codex/auth.json"
```

Normal Windows and Linux dual-bot installation remains unchanged.

## Verify

```bash
systemctl --user status codex-feishu-codex-balance-rotate.timer
journalctl --user -u codex-feishu-codex-balance-rotate.service -n 80
python3 scripts/codex-balance-rotate.py --dry-run
```

Expected:

- opentoken providers are listed with remaining balances;
- the highest-balance valid provider is selected;
- no API keys are printed.

## Attribution

This project is a deployment/configuration layer around
[cc-connect](https://github.com/chenhg5/cc-connect), which is MIT licensed.
See `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Full Changelog

See `CHANGELOG.md`.
