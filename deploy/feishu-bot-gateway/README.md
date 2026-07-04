# Feishu MMB Bot Gateway

Thin Feishu/Lark channel gateway for MMBAI. It keeps Feishu-specific event parsing, message sending, idempotency, and rate limiting outside Dify, while Dify workspace settings store Bot credentials and Dify app bindings.

## Runtime shape

- Private chat: every text message is handled.
- Group chat: only messages that mention the bot are handled.
- Gateway routing:
  - all text messages go to the Dify app bound as `主入口应用` by default; Dify decides intent and tool use
  - copywriting override is optional; when configured, copywriting requests are sent to that dedicated Dify app with the original user text
  - poster override is optional; when configured, poster requests use the existing `poster-service` async job and the result is uploaded to Feishu as an image

## Run

```bash
cp env.example .env
# fill Dify service URLs; Bot credentials are configured in Dify workspace settings -> 渠道接入
npx --yes pnpm@11.1.3 install --filter @mmb/feishu-bot-gateway...
npx --yes pnpm@11.1.3 --filter @mmb/feishu-bot-gateway build
npx --yes pnpm@11.1.3 --filter @mmb/feishu-bot-gateway start
```

Docker:

```bash
docker compose up -d --build
curl http://127.0.0.1:8096/health
```

Expose `POST /feishu-bot/events/{bot_id}` through HTTPS nginx. Copy the generated callback URL from Dify workspace settings -> 渠道接入 into the Feishu event subscription callback URL.

## Required Feishu permissions

Use an enterprise self-built Feishu app with bot enabled. Configure `APP_ID`, `APP_SECRET`, `Verification Token`, and `Encrypt Key` in Dify workspace settings -> 渠道接入, then subscribe to message receive events for private and group chats. The app needs permissions to read received text messages, send bot messages, and upload images used in messages.
