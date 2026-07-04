# Feishu MMB Bot Gateway

Thin Feishu/Lark channel gateway for MMBAI. It keeps Feishu-specific event parsing, message sending, idempotency, and rate limiting outside Dify, while reusing existing Dify apps and poster-service.

## Runtime shape

- Private chat: every text message is handled.
- Group chat: only messages that mention the bot are handled.
- Intent routing:
  - normal MMB chat -> `MMB智囊` through Dify Chat API
  - copywriting -> `MMB智囊` with a copywriting instruction prefix, or `DIFY_COPYWRITING_APP_API_KEY` if configured
  - poster -> existing `poster-service` async job; result is uploaded to Feishu and sent as an image

## Run

```bash
cp env.example .env
# fill Feishu and Dify secrets
npx --yes pnpm@11.1.3 install --filter @mmb/feishu-bot-gateway...
npx --yes pnpm@11.1.3 --filter @mmb/feishu-bot-gateway build
npx --yes pnpm@11.1.3 --filter @mmb/feishu-bot-gateway start
```

Docker:

```bash
docker compose up -d --build
curl http://127.0.0.1:8096/health
```

Expose `POST /feishu-bot/events` through HTTPS nginx and configure it as the Feishu event subscription callback URL.

## Required Feishu permissions

Use an enterprise self-built Feishu app with bot enabled. Configure `APP_ID`, `APP_SECRET`, `Verification Token`, and `Encrypt Key`, then subscribe to message receive events for private and group chats. The app needs permissions to read received text messages, send bot messages, and upload images used in messages.
