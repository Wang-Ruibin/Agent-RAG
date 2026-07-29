# Agent+RAG

Campus knowledge assistant built from citation-grounded RAG and a bounded,
read-only Agent. It is a separate repository from the original LLM+RAG project.

## What is included

- Direct RAG remains the default: FAISS + BM25 + RRF + reranking, with grounded
  `[S1]` citations and optional web-search fallback.
- Chat modes: `auto`, `rag`, and `agent`. Agent mode uses only allowlisted
  read tools, at most four tool calls, five LLM rounds, eight seconds per tool,
  and 45 seconds end-to-end. Built-in tools cover campus retrieval, policy
  comparison evidence, current date, document metadata, and scope-gated public
  Hohai web sources.
- Secret-safe Agent run traces and platform identity/session mappings.
- Bot management API and frontend route `/system/bot`.
- WeChat ClawBot/OpenClaw post-login protocol, official DingTalk Stream mode,
  and QQ OneBot v11 HTTP events. Bot credentials are encrypted at rest.
- Declarative discovery for future Skills, plugins, and MCP manifests. They do
  not execute automatically. Shell, arbitrary MCP, and filesystem-write tools
  are not exposed.

## Requirements

- Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 18+ for the frontend
- SQLite for local development or MySQL for deployment
- A configured OpenAI-compatible LLM endpoint (DeepSeek works out of the box)

## Run in WSL

```bash
cd /mnt/d/resource/research/RAG/Agent+RAG
cp .env.example .env
# Edit .env: set LLM_API_KEY (or legacy DEEPSEEK_API_KEY), JWT_SECRET,
# INITIAL_ADMIN_PASSWORD, and BOT_CREDENTIALS_ENCRYPTION_KEY.

uv sync --extra cpu
uv run alembic upgrade head

# If using the existing Java menu database, expose Bot management to admins.
mysql -u root -p campus_qa < campus-backend/sql/migrate-agent-rag.sql

# First run after adding knowledge documents.
uv run python -m app.cli index knowledge_docs --admin-email admin@campusqa.cn

# API: the terminal is ready when it prints http://127.0.0.1:8000.
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd /mnt/d/resource/research/RAG/Agent+RAG/campus-frontend
npm ci
npm run dev
```

Open the frontend address printed by Vite (normally `http://127.0.0.1:9090`).
`0.0.0.0` is a bind address, not the browser URL; the documented server command
uses loopback only.

## Bot setup

Generate the encryption key before creating any bot:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the result as `BOT_CREDENTIALS_ENCRYPTION_KEY`, restart the API, then use
the administrator bot-management page.

- WeChat: sign in using Tencent's official OpenClaw plugin. Add the returned
  `api_base_url`, `token`, `wechat_uin`, and `account_id` as bot credentials.
- DingTalk: create and authorize a custom app, then add `client_id` and
  `client_secret`.
- QQ: use a compliant OneBot v11 gateway. Add `api_base_url`, optional
  `access_token`, mandatory `webhook_secret`, and optional `self_id`; point the
  gateway at `/api/channels/qq-onebot/{bot_id}/events` with the
  `X-Onebot-Token` header.

See [platform instructions](docs/agent_platforms.md) and
[extension instructions](docs/extensions.md) for details.

## Verification

```bash
PYTHONPATH=backend pytest backend/tests/test_agent.py backend/tests/test_weixin_oc.py \
  backend/tests/test_dingtalk.py backend/tests/test_qq_onebot.py backend/tests/test_extensions.py

cd campus-frontend && npm run build
```

## License and third-party boundaries

This project is MIT-licensed. It does not contain AstrBot source code. AstrBot
was reviewed only as an architectural reference and is AGPL-3.0 licensed.
The Tencent OpenClaw WeChat plugin is an optional MIT-licensed dependency; it
is not vendored. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
