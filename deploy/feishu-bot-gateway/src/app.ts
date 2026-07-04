import express from "express";
import type { Express, Request } from "express";
import { loadConfig } from "./config.js";
import { DifyGateway } from "./difyGateway.js";
import type { RuntimeBotConfig } from "./difyGateway.js";
import { FeishuClient } from "./feishuClient.js";
import { decryptFeishuPayload, verifyFeishuSignature } from "./feishuCrypto.js";
import { extractMessageEvent } from "./feishuEvent.js";
import { selectMessageRoute } from "./routing.js";
import { createLogger } from "./logger.js";
import { PosterClient } from "./posterClient.js";
import { schedulePosterDelivery } from "./posterDelivery.js";
import { SlidingWindowRateLimiter, TtlSet } from "./state.js";

export const createApp = (): Express => {
  const config = loadConfig();
  const logger = createLogger(config.logLevel);
  const app = express();
  const idempotency = new TtlSet(config.idempotencyTtlMs);
  const limiter = new SlidingWindowRateLimiter(config.rateLimitWindowMs, config.rateLimitMaxMessages);
  const dify = new DifyGateway(config.dify);
  const poster = new PosterClient(config.poster.serviceUrl, config.poster.size);
  const runtimeCache = new RuntimeConfigCache(config.runtimeConfigCacheTtlMs);

  app.use(express.json({
    limit: "2mb",
    verify: (req: Request & { rawBody?: string }, _res, buf) => {
      req.rawBody = buf.toString("utf8");
    },
  }));

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "feishu-bot-gateway" });
  });

  app.post("/feishu-bot/events/:botId", async (req: Request & { rawBody?: string }, res) => {
    const botId = singleQueryValue(req.params.botId);
    const token = singleQueryValue(req.query.token);
    if (!botId) {
      res.status(400).json({ error: "missing bot id" });
      return;
    }
    try {
      const runtime = await runtimeCache.get(botId, token, () => dify.getRuntimeBotConfig(botId, token));
      const rawBody = req.rawBody ?? JSON.stringify(req.body ?? {});
      if (req.headers["x-lark-signature"] && !verifyFeishuSignature({
        encryptKey: runtime.encrypt_key,
        timestamp: req.headers["x-lark-request-timestamp"],
        nonce: req.headers["x-lark-request-nonce"],
        signature: req.headers["x-lark-signature"],
        body: rawBody,
      })) {
        logger.warn("invalid feishu signature", { botId });
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      let payload: any = req.body;
      if (payload.encrypt) {
        payload = decryptFeishuPayload(runtime.encrypt_key, payload.encrypt);
      }

      if (payload.type === "url_verification") {
        if (payload.token && payload.token !== runtime.verification_token) {
          res.status(401).json({ error: "invalid verification token" });
          return;
        }
        await dify.markVerified(botId, token).catch(error => logger.warn("mark verified failed", { botId, error: String(error) }));
        runtimeCache.delete(botId, token);
        res.json({ challenge: payload.challenge });
        return;
      }

      if (!runtime.enabled) {
        res.json({ ignored: true, reason: "bot disabled" });
        return;
      }

      const headerToken = payload.header?.token;
      if (headerToken && headerToken !== runtime.verification_token) {
        res.status(401).json({ error: "invalid event token" });
        return;
      }

      const message = extractMessageEvent(payload, {
        botOpenId: runtime.bot_open_id ?? undefined,
        botName: runtime.bot_name ?? runtime.name,
      });
      if (!message) {
        res.json({ ignored: true, reason: "not a text message event" });
        return;
      }

      res.json({ ok: true });
      const feishu = new FeishuClient(runtime.app_id, runtime.app_secret);
      void handleMessage({ message, feishu, dify, poster, idempotency, limiter, config, runtime, logger });
    } catch (error) {
      logger.error("event handling failed", { botId, error: error instanceof Error ? error.message : String(error) });
      res.status(500).json({ error: "internal error" });
    }
  });

  return app;
};

type HandleMessageParams = {
  message: NonNullable<ReturnType<typeof extractMessageEvent>>;
  feishu: FeishuClient;
  dify: DifyGateway;
  poster: PosterClient;
  idempotency: TtlSet;
  limiter: SlidingWindowRateLimiter;
  config: ReturnType<typeof loadConfig>;
  runtime: RuntimeBotConfig;
  logger: ReturnType<typeof createLogger>;
};

const handleMessage = async ({ message, feishu, dify, poster, idempotency, limiter, config, runtime, logger }: HandleMessageParams): Promise<void> => {
  try {
    if (!message.messageId || !message.chatId) return;
    if (!idempotency.add(message.messageId)) {
      logger.info("duplicate message ignored", { messageId: message.messageId, botId: runtime.id });
      return;
    }
    if (message.chatType !== "p2p" && !message.mentionedBot) return;
    if (message.messageType !== "text") {
      await feishu.sendText(message.chatId, "第一版先支持纯文本消息；图片和附件参考会在后续版本接入。");
      return;
    }
    if (!message.text) return;

    const rateKey = `${runtime.id}:${message.senderOpenId || message.chatId}`;
    if (!limiter.take(rateKey)) {
      await feishu.sendText(message.chatId, "请求太频繁了，请稍后再试。");
      return;
    }

    const user = `feishu:${runtime.id}:${message.senderOpenId}:${message.chatId}`;
    const route = selectMessageRoute(message.text, runtime);
    logger.info("message routed", { route: route.kind, overrideIntent: route.overrideIntent, chatType: message.chatType, messageId: message.messageId, botId: runtime.id });

    if (route.kind === "poster-service") {
      const job = await poster.createJob(message.text, message.messageId);
      await feishu.sendText(message.chatId, `已开始生成海报，job_id：${job.job_id}\n${job.estimated_time_text ?? "图片生成预计需要 5-10 分钟左右。"}`);
      schedulePosterDelivery({
        poster,
        feishu,
        chatId: message.chatId,
        job,
        pollIntervalMs: config.poster.pollIntervalMs,
        pollTimeoutMs: config.poster.pollTimeoutMs,
        logger,
      });
      return;
    }

    const binding = route.binding;
    if (!binding?.api_key) {
      await feishu.sendText(message.chatId, "这个 Bot 还没有绑定主入口 Dify 应用，请管理员在渠道接入里配置。");
      return;
    }

    const answer = await dify.chat(binding.api_key, message.text, user);
    await feishu.sendText(message.chatId, answer);
  } catch (error) {
    logger.error("message processing failed", { error: error instanceof Error ? error.message : String(error), messageId: message.messageId, botId: runtime.id });
    await feishu.sendText(message.chatId, "处理失败了，请稍后再试；如果持续失败，请联系管理员查看 feishu-bot-gateway 日志。").catch(() => undefined);
  }
};

class RuntimeConfigCache {
  private readonly values = new Map<string, { expiresAt: number; value: RuntimeBotConfig }>();

  constructor(private readonly ttlMs: number) {}

  async get(botId: string, token: string | undefined, loader: () => Promise<RuntimeBotConfig>): Promise<RuntimeBotConfig> {
    const key = this.key(botId, token);
    const cached = this.values.get(key);
    if (cached && cached.expiresAt > Date.now()) return cached.value;
    const value = await loader();
    this.values.set(key, { value, expiresAt: Date.now() + this.ttlMs });
    return value;
  }

  delete(botId: string, token: string | undefined): void {
    this.values.delete(this.key(botId, token));
  }

  private key(botId: string, token: string | undefined): string {
    return `${botId}:${token ?? ""}`;
  }
}

const singleQueryValue = (value: unknown): string | undefined => {
  if (Array.isArray(value)) return typeof value[0] === "string" ? value[0] : undefined;
  return typeof value === "string" && value ? value : undefined;
};
