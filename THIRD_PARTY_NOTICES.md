# Third-party notices

## AstrBot

This repository does not include, copy, or derive from AstrBot source code. Its
public documentation was consulted only for high-level interoperability and
product architecture research. AstrBot is licensed under AGPL-3.0; that license
does not apply to this independently implemented repository.

- Project: https://github.com/AstrBotDevs/AstrBot
- License: AGPL-3.0-only

## Tencent OpenClaw WeChat plugin

The optional personal-WeChat bridge is designed to interoperate with Tencent's
official `openclaw-weixin` protocol and plugin. No plugin source is vendored.
Operators install and manage that plugin separately under its MIT license.

- Project: https://github.com/Tencent/openclaw-weixin
- Package: `@tencent-weixin/openclaw-weixin`
- License: MIT

## Operator obligations

External bot credentials are encrypted at rest, are never returned by the API,
and must remain in local deployment configuration. Before enabling a platform,
review that platform's current terms, app-review rules, and user-consent
requirements.
