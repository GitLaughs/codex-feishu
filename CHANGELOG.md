# Changelog

All notable changes to this project will be documented in this file.

This project follows a lightweight Keep a Changelog style and uses semantic
versioning once public releases begin.

## [Unreleased]

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

- Codex API balance rotation script for cc-switch opentoken providers.
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
