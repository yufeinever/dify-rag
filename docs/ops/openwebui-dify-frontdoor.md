# OpenWebUI customer front door for Dify

This deployment keeps Dify as the AI backend and uses OpenWebUI only as the customer-facing chat and permission layer.

## Architecture

- Dify remains the source of truth for apps, workflows, agents, knowledge bases, model settings, and API keys.
- OpenWebUI provides login, customer groups, and a cleaner chat interface.
- Customer isolation is handled per customer or department by separate Dify apps/API keys plus OpenWebUI user/group visibility.
- Codex, WorkBuddy, and other tool clients should call Dify MCP/REST directly, not through OpenWebUI.

## Verified on T1000

- Dify version: `1.14.2`.
- OpenWebUI version: `v0.6.31`.
- OpenWebUI health check: `http://localhost:8088` returns `200 OK`.
- OpenWebUI container can reach Dify nginx through `http://nginx` and `http://docker-nginx-1`.
- Dify REST API was verified with app `专属智能客服` and returned the expected test answer.
- Dify MCP endpoint `POST /mcp/server/<server_code>/mcp` was verified with `initialize` and `tools/list`.
- Dify OpenAI-compatible app plugin is not installed yet; install it from Dify Marketplace before adding Dify apps as OpenWebUI OpenAI-compatible connections.
- OpenWebUI currently exposes five Pipe entries:
  - Dify apps: `每日新闻摘要-国内`, `专属智能客服`, `超级大脑`
  - Raw models from Dify provider credentials: `gpt-5.5`, `deepseek v4 flash`
- The raw model Pipes were verified with real chat completions and returned the expected test answer.

## Runtime

- Compose file: `deploy/openwebui/docker-compose.yaml`
- Private env file: `deploy/openwebui/.env`
- Container: `dify-openwebui`
- Default URL: `http://<t1000-host>:8088`
- Data volume: `dify-openwebui_openwebui-data`
- Dify internal network: `docker_default`

## Start and stop

```bash
cd /home/yu/projects/dify-rag/deploy/openwebui
cp env.example .env
# edit .env and set WEBUI_SECRET_KEY plus any Dify OpenAI-compatible endpoints
docker compose up -d
docker compose ps
curl -I http://localhost:8088
```

Stop:

```bash
cd /home/yu/projects/dify-rag/deploy/openwebui
docker compose down
```

## Dify app integration

Preferred path:

1. In Dify, create one app per customer/department and bind the correct knowledge base.
2. Install Dify Marketplace plugin `langgenius/oaicompat_dify_app` if it is not already installed.
3. Expose each Dify app through the plugin as an OpenAI-compatible endpoint.
4. Add the endpoint and API key to OpenWebUI as an OpenAI-compatible connection.
5. Use OpenWebUI admin/user-group permissions so each customer sees only their own entry.

Fallback path:

- If the OpenAI-compatible plugin is unavailable, use the Dify Service API directly through a minimal OpenWebUI Pipe/adapter.
- Keep that adapter thin: translate OpenAI chat messages to Dify `/v1/chat-messages` and return plain chat text only.

## Raw model integration

Customers may also need direct access to base models, not only Dify agents. On this deployment those entries are implemented as OpenWebUI Pipes that call the OpenAI-compatible upstream configured in Dify provider credentials.

Current raw model entries:

- `gpt-5.5`: calls upstream model `gpt-5.5`.
- `deepseek v4 flash`: calls upstream model `gpt-5.2`; this is the display name configured in Dify for the user's DeepSeek model.

Do not re-enable OpenWebUI's default OpenAI/Ollama discovery just to show these models. It previously made the admin panel slow because OpenWebUI tried to probe unused providers. Keep these environment defaults unless a deliberate provider migration is performed:

- `ENABLE_OPENAI_API=false`
- `ENABLE_OLLAMA_API=false`
- `ENABLE_DIRECT_CONNECTIONS=false`
- `ENABLE_BASE_MODELS_CACHE=false`
- `ENABLE_EVALUATION_ARENA_MODELS=false`

When adding a new raw model:

1. Add and test the provider credential in Dify first.
2. Read the Dify provider credential server-side and keep the API key in the OpenWebUI backend only.
3. Add one OpenWebUI Pipe with a customer-facing name.
4. Verify the Pipe with a real chat completion before exposing it to customer groups.

## MCP integration

Dify 1.14.2 in this deployment already has App MCP Server support in code and database.

Known current server:

- App: `专属智能客服`
- MCP endpoint shape: `POST /mcp/server/<server_code>/mcp`

Use MCP for Codex/WorkBuddy/tool clients. OpenWebUI MCP should be treated as optional customer-side tool expansion, not the main route to Dify agents.

## Security defaults

- `DEFAULT_USER_ROLE=pending`: newly registered users require admin approval.
- Workspace model/knowledge/prompt/tool/skill permissions are disabled by environment defaults.
- Keep Dify admin/API surfaces behind administrator access; expose OpenWebUI to customers instead.
- Never commit `deploy/openwebui/.env`; it contains the web UI secret and Dify API keys.