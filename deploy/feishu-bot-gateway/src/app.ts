import express from "express";
import type { Express, Request } from "express";
import { loadConfig } from "./config.js";
import { DifyGateway } from "./difyGateway.js";
import { FeishuClient } from "./feishuClient.js";
import { decryptFeishuPayload, verifyFeishuSignature } from "./feishuCrypto.js";
import { extractMessageEvent } from "./feishuEvent.js";
import { detectIntent, buildCopywritingPrompt } from "./intent.js";
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
  const feishu = new FeishuClient(config.feishu.appId, config.feishu.appSecret);
  const dify = new DifyGateway(config.dify);
  const poster = new PosterClient(config.poster.serviceUrl, config.poster.size);

  app.use(express.json({
    limit: "2mb",
    verify: (req: Request & { rawBody?: string }, _res, buf) => {
      req.rawBody = buf.toString("utf8");
    },
  }));

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "feishu-bot-gateway" });
  });

  app.post("/feishu-bot/events", async (req: Request & { rawBody?: string }, res) => {
    try {
      const rawBody = req.rawBody ?? JSON.stringify(req.body ?? {});
      if (req.headers["x-lark-signature"] && !verifyFeishuSignature({
        encryptKey: config.feishu.encryptKey,
        timestamp: req.headers["x-lark-request-timestamp"],
        nonce: req.headers["x-lark-request-nonce"],
        signature: req.headers["x-lark-signature"],
        body: rawBody,
      })) {
        logger.warn("invalid feishu signature");
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      let payload: any = req.body;
      if (payload.encrypt) {
        payload = decryptFeishuPayload(config.feishu.encryptKey, payload.encrypt);
      }

      if (payload.type === "url_verification") {
        if (payload.token && payload.token !== config.feishu.verificationToken) {
          res.status(401).json({ error: "invalid verification token" });
          return;
        }
        res.json({ challenge: payload.challenge });
        return;
      }

      const headerToken = payload.header?.token;
      if (headerToken && headerToken !== config.feishu.verificationToken) {
        res.status(401).json({ error: "invalid event token" });
        return;
      }

      const message = extractMessageEvent(payload, {
        botOpenId: config.feishu.botOpenId,
        botName: config.feishu.botName,
      });
      if (!message) {
        res.json({ ignored: true, reason: "not a text message event" });
        return;
      }

      res.json({ ok: true });
      void handleMessage({ message, feishu, dify, poster, idempotency, limiter, config, logger });
    } catch (error) {
      logger.error("event handling failed", { error: error instanceof Error ? error.message : String(error) });
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
  logger: ReturnType<typeof createLogger>;
};

const handleMessage = async ({ message, feishu, dify, poster, idempotency, limiter, config, logger }: HandleMessageParams): Promise<void> => {
  try {
    if (!message.messageId || !message.chatId) return;
    if (!idempotency.add(message.messageId)) {
      logger.info("duplicate message ignored", { messageId: message.messageId });
      return;
    }
    if (message.chatType !== "p2p" && !message.mentionedBot) return;
    if (message.messageType !== "text") {
      await feishu.sendText(message.chatId, "第一版先支持纯文本消息；图片和附件参考会在后续版本接入。");
      return;
    }
    if (!message.text) return;

    const rateKey = message.senderOpenId || message.chatId;
    if (!limiter.take(rateKey)) {
      await feishu.sendText(message.chatId, "请求太频繁了，请稍后再试。");
      return;
    }

    const user = `feishu:${message.senderOpenId}:${message.chatId}`;
    const intent = detectIntent(message.text);
    logger.info("message routed", { intent, chatType: message.chatType, messageId: message.messageId });

    if (intent === "poster") {
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

    const answer = intent === "copywriting"
      ? await dify.copywrite(buildCopywritingPrompt(message.text), user)
      : await dify.chat(message.text, user);
    await feishu.sendText(message.chatId, answer);
  } catch (error) {
    logger.error("message processing failed", { error: error instanceof Error ? error.message : String(error), messageId: message.messageId });
    await feishu.sendText(message.chatId, "处理失败了，请稍后再试；如果持续失败，请联系管理员查看 feishu-bot-gateway 日志。").catch(() => undefined);
  }
};
