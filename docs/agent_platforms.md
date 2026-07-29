# Agent and platform integration

## Chat modes

`POST /api/chat` and `POST /api/chat/stream` accept `mode`:

- `auto` (default): deterministic router uses Agent for multi-step or
  time-sensitive wording and otherwise uses direct RAG.
- `rag`: preserve the existing direct retrieval-and-generation path.
- `agent`: execute only allowlisted read tools, then use their validated
  evidence in the same citation-grounded RAG answer path.

The streaming API emits `route` and `agent_step` events. It intentionally does
not expose prompts, model reasoning, or raw tool output. Run traces are
available to the conversation owner or an administrator at
`GET /api/agent/runs/{run_id}`.

## Security boundaries

- Agent tools are sequential, read-only, JSON-validated, capped at four calls,
  and have an eight-second per-tool / 45-second total budget.
- `AgentRun`/`AgentStep` records store only status, summaries, and duration.
  Raw documents, tool results, prompts, and credentials are excluded.
- Set `BOT_CREDENTIALS_ENCRYPTION_KEY` to a Fernet key before creating bots.
  The API never returns decrypted credentials.
- Python, shell, filesystem write, MCP process execution, and plugin code are
  not Agent tools. They remain disabled until the optional sandbox milestone.

## Built-in Agent tools

- `search_campus_knowledge`: bounded search over the local citation index.
- `get_document_metadata` and `retrieve_document_evidence`: metadata and
  evidence reads constrained to known document IDs.
- `compare_policies`: retrieves attributable policy material for a comparison;
  it never invents or decides the comparison itself.
- `get_current_date`: server time in `Asia/Shanghai`.
- `search_public_web`: invokes the existing public web provider only for
  Hohai-related questions and returns bounded structured source fields.

Policy/comparison wording selects `compare_policies` in the default Agent
plan. Public-web search remains subject to the same Hohai scope gate and final
`[Sx]`/`[Wx]` citation validation as direct RAG.

## WeChat ClawBot / OpenClaw

The `WEIXIN_OC` adapter implements the documented post-login Tencent
OpenClaw-WeChat HTTP protocol: `getupdates` long polling, context-token-aware
`sendmessage`, and text/image/video/file message recognition.

1. Install the official plugin separately:
   `openclaw plugins install @tencent-weixin/openclaw-weixin`
2. Scan with the official command shown by the bot login endpoint:
   `openclaw channels login --channel openclaw-weixin`
3. Create a `WEIXIN_OC` bot and provide the post-login connection values in its
   encrypted credentials (`api_base_url`, `token`, `wechat_uin`, `account_id`).
4. Start it through `POST /api/admin/bots/{id}/start`.

The QR credential is not persisted by this application. The OpenClaw plugin is
an optional MIT-licensed dependency; no plugin or AstrBot source is vendored.

## QQ OneBot v11

The `QQ_ONEBOT` adapter is a standard OneBot v11 HTTP integration. It does not
ship, drive, or authenticate a QQ client. Use a compliant gateway that you
operate and configure it as follows:

1. Create a `QQ_ONEBOT` bot with encrypted credentials: `api_base_url`, the
   optional outbound `access_token`, mandatory `webhook_secret`, and optional
   `self_id` for group-mention detection.
2. Start the bot. Configure the gateway's HTTP POST event callback as
   `POST /api/channels/qq-onebot/{bot_id}/events` and set the
   `X-Onebot-Token` header to `webhook_secret`.
3. Private and group text messages are mapped to regular campus conversations;
   replies use OneBot's `/send_private_msg` or `/send_group_msg` endpoint.

The event token is checked with a constant-time comparison. It is not exposed
by administration APIs or written to message records.

## DingTalk

The `DINGTALK` adapter uses the official `dingtalk-stream` SDK in Stream mode.
Create and authorize a custom app in the DingTalk developer console, then save
its `client_id` and `client_secret` as encrypted credentials and start it from
the bot-management page. The SDK maintains the authenticated long connection;
messages and replies pass through the same identity, session, group-rule, and
RAG pipeline as the other platforms.

## Platform account behavior

On the first valid external message, the system creates a regular `STUDENT`
user with a synthetic internal email, binds `PlatformIdentity`, and maps the
private or group thread to `PlatformSession`. Message IDs are deduplicated.
Group messages require a mention or configured prefix by default.

## Existing Java menu database

The Python API enforces administrator access for bot administration. If the
Vue sidebar menu comes from the existing Java `campus_qa` database, apply
`campus-backend/sql/migrate-agent-rag.sql` once. It adds the `/system/bot`
entry only for the administrator role; it does not grant any platform
credentials or bot permissions to normal users.
