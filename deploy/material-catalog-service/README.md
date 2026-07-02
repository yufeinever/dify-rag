# Material Catalog Service

Read-only OpenAPI tool service for the Dify "资料全知agent". It follows the OpenMetadata-style asset catalog pattern at a small scope: discover material assets, profile file inventory, map Dify datasets/documents to upload files, and recommend preprocessing actions.

The service only reads the Dify app volume and Dify Postgres. It writes its own SQLite catalog under `./catalog` for incremental scan state.

## Production defaults

- Dify app volume: `/opt/mmb-dify/current/docker/volumes/app`
- Container app root: `/dify-app`
- Default scan roots: `storage,.`
- Dify network: `mmb-dify-v010_default`
- Service URL from Dify containers: `http://material-catalog-service:8091`

## Run

```bash
cp .env.example .env
# fill DIFY_DB_PASSWORD from the Dify docker env
docker compose up -d --build
curl http://127.0.0.1:8091/health
```

Import `openapi-dify.yaml` as a Dify OpenAPI tool provider.
