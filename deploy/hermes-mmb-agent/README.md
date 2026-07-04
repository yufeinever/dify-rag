# Hermes MMB Agent

This directory is the first-stage validation stack for the Hermes version of `MMB企业主助手`.

It keeps Dify as the backend capability system and validates Hermes as the master Agent runtime through Hermes API Server, Hermes Dashboard, and Open WebUI.

## Services

- `hermes-agent`: Hermes runtime and OpenAI-compatible API server.
- `open-webui`: manual chat validation entry connected to Hermes.
- `mmb-capability-center`: runs separately and exposes MMB enterprise tools over `/mcp`.

## First Run

```bash
cp .env.example .env
# Fill OPENAI_API_BASE_URL, OPENAI_API_KEY, CAPABILITY_AUTH_TOKEN.
scripts/fetch-hermes.sh
docker compose config
docker compose build hermes-agent
docker compose up -d
```

Validation URLs:

- Open WebUI: `http://<host>:3008`
- Hermes API Server: `http://<host>:8642/v1`
- Hermes Dashboard: `http://<host>:9119`

## Validation Rule

Do not route the first-stage test through Dify Studio. Use Open WebUI or Hermes native UI/API so the test measures Hermes itself, not a Dify-Agent-to-Hermes wrapper.

Compare the same task set against:

- Current Dify `MMB智囊`
- Hermes profile `MMB企业主助手`

Track tool-call accuracy, empty/old tool-name errors, latency, context behavior, and whether enterprise-private data only goes through MMB MCP.
