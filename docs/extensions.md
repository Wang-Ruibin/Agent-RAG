# Agent extensions

Agent extensions are declarative by default. Place a `manifest.json` under one
of `data/extensions/{skills,plugins,mcp}/<name>/`. A minimal manifest is:

```json
{"name":"example","version":"1.0.0","description":"What it provides"}
```

Administrators can inspect discovered manifests at `GET /api/admin/extensions`.
Discovery never imports Python, starts an MCP process, accepts a network tool,
or grants a plugin access to credentials. This separates a future approval
workflow from the normal RAG service.

LLM configuration is OpenAI-compatible: set `LLM_API_KEY`, `LLM_BASE_URL`, and
`LLM_MODEL` for a compatible provider, or retain `DEEPSEEK_API_KEY` for
backward-compatible DeepSeek configuration. RAG grounding applies regardless
of provider.

`AGENT_SANDBOX_ENABLED` is false by default. It is only a configuration guard;
this repository does not expose shell, filesystem-write, container, or
arbitrary MCP execution tools.
