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

## Platform account behavior

On the first valid external message, the system creates a regular `STUDENT`
user with a synthetic internal email, binds `PlatformIdentity`, and maps the
private or group thread to `PlatformSession`. Message IDs are deduplicated.
Group messages require a mention or configured prefix by default.
