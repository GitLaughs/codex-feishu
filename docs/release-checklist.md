# Release Checklist

Use this before publishing a GitHub release.

## Local Checks

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
git status --short
```

When bash is available, also run:

```bash
bash ./scripts/test-linux.sh
```

Confirm:

- no generated `config.toml`;
- no app secrets;
- no private open IDs or group chat IDs;
- no local workspace data;
- README quick start is current;
- CHANGELOG has the release entry.
- NOTICE and THIRD_PARTY_NOTICES.md include dependency attribution.
- cc-connect attribution and MIT license reference are present.

## Version

For the first release:

```powershell
git tag v0.1.0
git push origin main --tags
```

## GitHub Release Page

Use the draft in [RELEASE_DRAFT.md](../RELEASE_DRAFT.md), or use GitHub's
generated release notes with `.github/release.yml`.

Recommended sections:

- Overview
- Highlights
- Install
- Feishu console checklist
- Verification
- Known limitations
- Full changelog

## After Publish

- Test the README quick start from a clean folder.
- Create one normal group-message test.
- Create one @ deep-message test.
- Verify no terminal windows appear for hooks.
