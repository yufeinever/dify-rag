# LobeChat Full PoC

This deployment is the full-stack LobeChat evaluation environment for comparing
LobeChat against OpenWebUI and LibreChat as a customer-facing AI workspace.

## Runtime

- URL: `http://192.168.31.53:3211`
- Compose directory: `/home/yu/projects/dify-rag/deploy/lobechat-full`
- Main container: `dify-lobechat-full`
- Object storage: RustFS on `9020`, console on `9021`
- Database: ParadeDB/PostgreSQL with local bind data under `data/postgres`
- Cache: Redis with local bind data under `data/redis`

The original lightweight LobeChat PoC remains available on `3210`.

## Model Gateway

The full PoC connects to the existing OpenAI-compatible gateway:

```env
OPENAI_PROXY_URL=http://118.196.65.83:8080/v1
OPENAI_MODEL_LIST=-all,+gpt-5.5,+gpt-5.2=deepseek v4 flash
DEFAULT_AGENT_CONFIG=model=gpt-5.5;provider=openai
SYSTEM_AGENT=default=openai/gpt-5.5
```

`deepseek v4 flash` is a display alias for the upstream model id `gpt-5.2`.

## Enabled Workspace Features

```env
ENABLED_UPLOAD=1
ENABLED_KNOWLEDGE_BASE=1
ENABLED_MCP=1
ENABLED_ARTIFACTS=1
ENABLED_WEB_SEARCH=1
```

Verified in the UI:

- The home model selector shows `GPT-5.5` and `deepseek v4 flash`.
- The default chat model is `GPT-5.5`.
- The context menu shows attachments, memory, web search, and skills.
- The Resource page shows file upload, folder upload, and resource library creation.

## Notes

- `.env` is intentionally ignored because it contains secrets.
- `data/` is intentionally ignored because it contains runtime database and
  object-storage state.
- This is still a PoC. Dify Agents are not automatically imported into
  LobeChat Agents; that needs a Dify OpenAI-compatible app endpoint or a thin
  bridge per Dify App.
