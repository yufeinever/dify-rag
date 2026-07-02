# Material Catalog Service

Read-only OpenAPI and MCP tool service for the Dify "资料全知agent".

v2 exposes low-level material exploration tools over MCP so Dify Agent/function-call mode can decide which tools to call. It keeps the v1 HTTP/OpenAPI endpoints for compatibility.

The service only reads the Dify app volume and Dify Postgres. It writes its own SQLite catalog under `./catalog` for incremental scan state and generated media thumbnails under `./catalog/media-cache`.

For media display, the MCP response stays structured: Dify upload images get `thumbnail_url`, `thumbnail_markdown_image`, `original_preview_url`, and `original_link_markdown`. `markdown_image` is kept as a compatibility alias and points to the thumbnail when available. Markdown files are read as text with `render_as=markdown`; the agent should output them as Markdown instead of flattening them into plain text.

## MCP tools

- `server_info`
- `list_material_roots`
- `list_datasets`
- `list_documents`
- `search_segments`
- `read_document_chunks`
- `search_files` - image upload results include `thumbnail_markdown_image` for fast Dify chat rendering and `original_link_markdown` for source verification
- `read_file_text` - Markdown files return `render_as=markdown` so the agent can preserve headings, lists, tables, and image syntax
- `profile_materials`
- `list_material_changes`

## Production defaults

- Dify app volume: `/opt/mmb-dify/current/docker/volumes/app`
- Container app root: `/dify-app`
- Default scan roots: `storage,.`
- Dify network: `mmb-dify-v010_default`
- Service URL from Dify containers: `http://material-catalog-service:8091`
- Optional image rendering secret: `DIFY_FILE_PREVIEW_SECRET_KEY`, set to the same value as the Dify API `SECRET_KEY` so `markdown_image` URLs can be opened by the Dify frontend.
- Thumbnail public prefix: `/material-agent/media`, reverse-proxied by Dify nginx to this service's `/media` endpoint.
- Thumbnail defaults: longest side `1024px`, WebP quality `78`, signature TTL `300s`.

## Run

```bash
cp .env.example .env
# fill DIFY_DB_PASSWORD from the Dify docker env
docker compose up -d --build
curl http://127.0.0.1:8091/health
```

## MCP smoke test

```bash
curl -s -X POST http://127.0.0.1:8091/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Dify registration

The Dify API container's MCP client goes through the SSRF proxy. If an upstream proxy is configured, set this in `docker/.env` and recreate `ssrf_proxy` so internal MCP service names go direct:

```bash
SSRF_DIRECT_HOSTS=material-catalog-service
```

Then run the registration script inside the Dify API container:

```bash
docker cp scripts/register_dify_agent.py docker-api-1:/tmp/register_dify_agent.py
docker exec docker-api-1 bash -lc \
  'cd /app/api && PYTHONPATH=/app/api /app/api/.venv/bin/python /tmp/register_dify_agent.py'
```

This registers the MCP provider `资料全知材料探索`, configures `资料全知agent` as an `agent-chat` app, enables all MCP tools, and installs the app in Explore.
