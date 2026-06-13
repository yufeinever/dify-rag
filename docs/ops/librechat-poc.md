# LibreChat PoC on T1000

LibreChat is deployed as a customer-front-door candidate to compare against OpenWebUI.

## Runtime

- Source snapshot: `deploy/librechat/LibreChat`
- Compose file: `deploy/librechat/LibreChat/docker-compose.poc.yaml`
- Private env file: `deploy/librechat/LibreChat/.env`
- Config file: `deploy/librechat/LibreChat/librechat.yaml`
- URL: `http://<t1000-host>:3090`
- Local health check: `curl -I http://localhost:3090/`

## Containers

- `librechat-nginx`: exposes `3090:80`
- `librechat-api`: LibreChat API and web app backend
- `librechat-mongodb`: conversation and user data
- `librechat-meilisearch`: search index
- `librechat-rag-api`: LibreChat RAG service for PoC features
- `librechat-vectordb`: pgvector backend for LibreChat RAG

## Current model setup

The PoC uses LibreChat custom OpenAI-compatible endpoint configuration.

Current endpoint label: `企业模型`

Current models:

- `gpt-5.5`
- `gpt-5.2`

The upstream API key and base URL are copied from the Dify provider credential into `.env`. Do not commit `.env`.

## Start and stop

```bash
cd /home/yu/projects/dify-rag/deploy/librechat/LibreChat
docker compose -f docker-compose.poc.yaml up -d
docker compose -f docker-compose.poc.yaml ps
curl -I http://localhost:3090/
```

Stop:

```bash
cd /home/yu/projects/dify-rag/deploy/librechat/LibreChat
docker compose -f docker-compose.poc.yaml down
```

## Boundaries

This is only a PoC for the front-end experience.

- It does not replace Dify as the AI backend.
- It currently exposes raw models, not Dify Agent apps.
- Dify Agent integration should use Dify's OpenAI-compatible app plugin or a thin bridge before production use.
- LibreChat's own RAG is running for feature evaluation, but enterprise knowledge should still stay in Dify unless a migration decision is made.

## Verified

- LibreChat login page loads at `http://192.168.31.53:3090/login`.
- Email login and registration are enabled for initial PoC testing.
- Social login buttons are disabled.
- LibreChat config loads the custom endpoint from `librechat.yaml`.
