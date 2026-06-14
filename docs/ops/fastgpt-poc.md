# FastGPT Full PoC

This deployment is a full FastGPT evaluation stack on T1000.

## Runtime

- URL: `http://192.168.31.53:3020`
- Compose directory: `/home/yu/projects/dify-rag/deploy/fastgpt`
- Root user: `root`
- Root password: stored only in `/home/yu/projects/dify-rag/deploy/fastgpt/.env`
- MCP/SSE port: `3025`
- MinIO/S3 endpoint: `http://192.168.31.53:9030`
- MinIO console: `http://192.168.31.53:9031`

## Components

The PoC uses the official FastGPT PgVector Docker Compose stack:

- FastGPT app `v4.14.22`
- MongoDB replica set
- Redis
- PgVector
- MinIO
- FastGPT plugin service
- FastGPT code sandbox
- OpenSandbox service
- FastGPT MCP server
- AIProxy + AIProxy PostgreSQL

## Port Mapping

- FastGPT app: `3020:3000`
- MCP server: `3025:3000`
- MinIO API: `9030:9000`
- MinIO console: `9031:9001`

## Model Gateway

Existing OpenAI-compatible gateway details are recorded in `.env` only:

- `OPENAI_COMPATIBLE_BASE_URL=http://118.196.65.83:8080/v1`
- `OPENAI_COMPATIBLE_API_KEY=...`

The initial deployment starts with no active FastGPT models. Configure models in
FastGPT/AIProxy after login, or pre-seed AIProxy channels separately.

## Verification

Verified on 2026-06-14:

- `http://localhost:3020/` returns HTTP 200.
- `fastgpt-app` logs show root user initialized and system initialization success.
- All core containers are running or healthy.
- Login page is visible at `http://192.168.31.53:3020/login`.

## Notes

- `.env` is ignored because it contains secrets.
- This is an independent FastGPT PoC, not a Dify frontend.
