FROM node:22-alpine

RUN apk add --no-cache git

WORKDIR /app
RUN corepack enable && corepack pnpm config set registry https://registry.npmmirror.com

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY sdks/nodejs-client ./sdks/nodejs-client
COPY deploy/feishu-bot-gateway ./deploy/feishu-bot-gateway

RUN corepack pnpm install --filter @mmb/feishu-bot-gateway... --no-frozen-lockfile
RUN corepack pnpm --filter dify-client build
RUN corepack pnpm --filter @mmb/feishu-bot-gateway build

WORKDIR /app/deploy/feishu-bot-gateway
ENV NODE_ENV=production
EXPOSE 8096
CMD ["node", "dist/index.js"]
