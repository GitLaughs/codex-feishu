# Changelog

All notable changes to this project will be documented in this file.

This project follows a lightweight Keep a Changelog style and uses semantic
versioning once public releases begin.

## [Unreleased]

## [0.8.0] - 2026-05-24

### Added

- Added `scripts/bootstrap-linux.sh` as a beginner Ubuntu bootstrap script for
  apt dependencies, optional swap, Node.js 22, pinned Codex/cc-connect global
  installs, and clone/update of the public repository.
- Added v0.8.0 release notes covering the cloud Linux baseline and install
  workflow split between host bootstrap and Feishu credential configuration.

### Changed

- Updated Linux documentation and README install guidance to point beginners at
  `bootstrap-linux.sh` before running the interactive `install-linux.sh`.
- Clarified that bootstrap never writes Feishu app secrets, API keys, user IDs,
  group IDs, or generated cc-connect runtime config.
- Made Linux smoke tests choose `python3` or `python` so Git Bash environments
  with a broken `python3` alias can still validate scripts.

## [0.7.0] - 2026-05-24

### Added

- Added generated `workspace_manifest.json` with active commands, planned commands, data sources, guardrails, and resource policy.
- Added deterministic SQLite/FTS5 read-only command scripts for `/files`, `/memfind`, `/knowledge`, `/tasks`, `/workspace-info`, and `/status-index`.
- Added `/health-codex-feishu` command plus manifest, help, file, memory, and run-log redaction health checks.
- Added `docs/memory-file-optimization-plan.md` for the memory and file management roadmap.
- Added installer smoke coverage for generated manifests, deterministic commands, local reindex, command isolation, and health checks.
- Added `docs/product-iteration-plan.md` with a P0-P3 codex-feishu hardening roadmap.
- Added `docs/optimization-report-2026-05-23.md` with current server status and next operational priorities.
- Added `scripts/audit-secrets.ps1` for pre-release secret scanning.
- Added `scripts/codex-feishu-healthcheck.sh` for server-side systemd, project-count, resource, and recent-error checks.

### Changed

- `/remember`, `/forget`, `/memory review`, and write-oriented file commands are now documented as planned commands rather than active commands until confirmation and audit flows exist.

## [0.6.0] - 2026-05-23

### Added

- Platform image-generation command templates for Feishu `/画图`, `/生图`, `/img`, `画图`, and `生图`.
- Shared `scripts/generate-image.js` helper with `FEISHU_IMAGE_*` environment overrides and OpenAI-compatible Images/Responses API support.
- Installer smoke coverage for copying the image helper and generating `image_command_enabled` platform options.

## [0.5.0] - 2026-05-23

### Added

- Optional family memory capture workflow for explicit remember, forget, task, shopping-list, and memory-read messages.
- Windows installer flag `-EnableFamilyMemory` and Linux installer flag `--enable-family-memory`.
- Platform-layer deep acknowledgement generation through `instant_ack_text`.
- Family memory smoke tests for direct capture and hook execution.
- Codex provider rotation fallback for providers that do not support the Responses API.

### Changed

- Double-bot templates no longer use the legacy `message.received` acknowledgement hook by default.
- README and install docs now describe the current reproducible dual-bot flow, including mention routing, platform acknowledgements, optional family memory, and cc-switch provider rotation.
- Codex balance rotation now treats cc-switch Codex entries as generic providers instead of filtering to a single provider domain.

### Fixed

- Kept immediate deep acknowledgements out of terminal/hook scripts so Feishu receives acknowledgement from the platform route.

## [0.4.1] - 2026-05-23

### Fixed

- Restored immediate acknowledgement delivery by retrying `cc-connect send` briefly when hooks fire before a session is ready.
- Changed the acknowledgement text to `收到正在输出，请等等我。`.

## [0.4.0] - 2026-05-23

### Added

- Optional mini route guard generation through `ignore_bot_mentions` for runtimes that support dropping deep bot mentions before mini routing.
- Windows installer parameter `-MiniIgnoreBotMentions`.
- Linux installer flag `--mini-ignore-bot-mentions`.
- Test coverage and docs for deep mention/topic silence in all-message mini deployments.

## [0.3.0] - 2026-05-23

### Added

- Codex API balance rotation script for cc-switch providers with an OpenAI-compatible usage endpoint.
- Optional Linux installer flags to register a systemd user timer for Codex API balance rotation.
- Documentation for the rotation behavior and its non-retry boundary.

## [0.2.0] - 2026-05-23

### Added

- Linux installer, runner, ack hook, helper scripts, and Linux TOML template.
- systemd user service support for Linux deployments.
- Linux install guide and Linux CI validation.
- Cross-platform release docs while preserving Windows PowerShell deployment.

## [0.1.2] - 2026-05-22

### Added

- Generated group `AGENTS.md` with privacy boundaries, `NO_REPLY` silence rules, and deep/mini routing rules.
- Static `/help` command and `/dream` workspace maintenance command.
- Feishu/Lark helper scripts for resource download, bounded event listening, and redacted health checks.
- Generated help guide, dream prompt, memory folders, and richer workspace bootstrap.

### Changed

- Mini hook no longer sends immediate `收到` by default; mini only acknowledges after deciding to handle a normal message.
- Group projects now disable privileged cc-connect management commands by default.
- Startup script now prefers the packaged `cc-connect.exe` and falls back to `cc-connect.cmd`.

## [0.1.1] - 2026-05-22

### Added

- Configurable `gpt-5.4-mini` reply trigger threshold for all-message group monitoring.
- Strict default policy for mini replies so casual chat and standalone question marks stay silent.
- Installer and documentation coverage for `-MiniTriggerThreshold`.

## [0.1.0] - 2026-05-22

### Added

- Dual Feishu bot cc-connect config template.
- Interactive and non-interactive Windows installer.
- Hidden cc-connect runner and watchdog scripts.
- Hidden acknowledgement hook wrapper.
- File import and local index helper.
- Group workspace instruction template.
- GitHub release configuration, issue templates, CI, and release checklist.
- Third-party notices and attribution for cc-connect and related platforms.
