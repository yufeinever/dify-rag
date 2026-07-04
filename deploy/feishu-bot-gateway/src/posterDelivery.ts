import type { Logger } from "./logger.js";
import type { FeishuClient } from "./feishuClient.js";
import type { PosterClient, PosterJob } from "./posterClient.js";

export const schedulePosterDelivery = (params: {
  poster: PosterClient;
  feishu: FeishuClient;
  chatId: string;
  job: PosterJob;
  pollIntervalMs: number;
  pollTimeoutMs: number;
  logger: Logger;
}): void => {
  const startedAt = Date.now();
  const poll = async (): Promise<void> => {
    try {
      const latest = await params.poster.getJob(params.job.job_id);
      if (latest.status === "succeeded" && latest.poster_url) {
        await params.feishu.sendText(params.chatId, `海报已生成，job_id：${latest.job_id}`);
        await params.feishu.sendImageFromUrl(params.chatId, latest.poster_url);
        return;
      }
      if (latest.status === "failed") {
        await params.feishu.sendText(params.chatId, `海报生成失败：${latest.error ?? "未知错误"}`);
        return;
      }
      if (Date.now() - startedAt >= params.pollTimeoutMs) {
        await params.feishu.sendText(params.chatId, `海报仍在生成中，请稍后用 job_id 查询：${latest.job_id}`);
        return;
      }
      setTimeout(poll, params.pollIntervalMs).unref();
    } catch (error) {
      params.logger.error("poster poll failed", { error: error instanceof Error ? error.message : String(error), jobId: params.job.job_id });
      if (Date.now() - startedAt < params.pollTimeoutMs) {
        setTimeout(poll, params.pollIntervalMs).unref();
      }
    }
  };
  setTimeout(poll, params.pollIntervalMs).unref();
};
