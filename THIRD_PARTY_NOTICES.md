# Third-Party Notices

This project is a configuration and automation layer around existing tools and
platform APIs. It does not claim ownership over those tools or services.

## cc-connect

- Project: `cc-connect`
- Repository: <https://github.com/chenhg5/cc-connect>
- License: MIT
- Usage: invoked as a local CLI and configured through generated `config.toml`.
- Notes: `codex-feishu` was built around cc-connect features such as Feishu
  support, lifecycle hooks, stream preview, session isolation, and scheduled
  background operation.

## Feishu / Lark

- Product/API: Feishu/Lark Open Platform
- Website: <https://open.feishu.cn/>
- Usage: users create and configure their own Feishu apps and bot permissions.
- Notes: Feishu/Lark terms and app-review requirements apply separately.

## OpenAI Codex / GPT Models

- Product/API: OpenAI Codex and GPT models
- Website: <https://openai.com/>
- Usage: model names are passed through cc-connect/Codex configuration.
- Notes: OpenAI service terms apply separately.

## GitHub Actions

- Product: GitHub Actions
- Website: <https://github.com/features/actions>
- Usage: CI workflow in `.github/workflows/ci.yml`.

## License Boundary

The MIT License in this repository covers only files committed to this
repository. Dependencies and external services remain under their own licenses
and terms.
