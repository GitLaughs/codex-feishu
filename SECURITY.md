# Security Policy

## Supported Versions

This project is pre-1.0. Security fixes should target `main` until versioned
releases begin.

## Sensitive Data

Do not open public issues or pull requests containing:

- Feishu/Lark app secrets;
- access tokens;
- app IDs from private deployments if they identify an internal app;
- user open IDs;
- group chat IDs;
- generated `~/.cc-connect/config.toml`;
- chat logs or private files.

## Reporting a Vulnerability

If a vulnerability may expose credentials or private chat content, report it
privately through GitHub Security Advisories after the repository is published.

If Security Advisories are not enabled yet, contact the maintainer privately and
share only the minimum reproduction details needed to confirm the issue.

## Local Execution Model

The installer writes local scheduled tasks and runs local PowerShell scripts.
Review scripts before running them in shared or managed Windows environments.
