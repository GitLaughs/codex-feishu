# Contributing

Contributions are welcome once the repository is published.

## Development Setup

```powershell
git clone <repo-url>
cd codex-feishu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

The test script checks:

- PowerShell parser errors;
- placeholder leakage in templates;
- known local secret patterns;
- install smoke generation with fake credentials.

## Pull Requests

Keep pull requests focused. Include:

- what changed;
- why the change is needed;
- how it was tested;
- any compatibility notes for existing cc-connect configs.

Do not include real Feishu app secrets, app IDs from private deployments, user
open IDs, group chat IDs, or generated local config.

## Coding Style

- Prefer plain PowerShell 5.1 compatible syntax.
- Keep scripts inspectable and avoid hidden network calls.
- Use explicit parameters for install automation.
- Avoid destructive filesystem operations.

## Release Notes

Use labels that match `.github/release.yml` where possible:

- `feature`
- `fix`
- `docs`
- `security`
- `maintenance`
- `breaking`
