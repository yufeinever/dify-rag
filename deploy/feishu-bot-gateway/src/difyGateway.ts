import { ChatClient } from "../../../sdks/nodejs-client/dist/index.mjs";
import type { JsonObject } from "../../../sdks/nodejs-client/dist/index.mjs";

export type ChannelIntegrationPurpose = "default" | "copywriting" | "poster";

export type RuntimeAppBinding = {
  app_id: string;
  app_name: string;
  api_key?: string | null;
};

export type RuntimeBotConfig = {
  id: string;
  tenant_id: string;
  name: string;
  channel: "feishu";
  enabled: boolean;
  app_id: string;
  app_secret: string;
  verification_token: string;
  encrypt_key: string;
  bot_name?: string | null;
  bot_open_id?: string | null;
  bindings: Partial<Record<ChannelIntegrationPurpose, RuntimeAppBinding>>;
};

export type DifyGatewayConfig = {
  baseUrl: string;
  consoleApiBaseUrl: string;
};

const answerFromResponse = (data: JsonObject): string => {
  const answer = data.answer;
  if (typeof answer === "string" && answer.trim()) return answer;
  const text = data.text;
  if (typeof text === "string" && text.trim()) return text;
  return JSON.stringify(data, null, 2);
};

const cleanBaseUrl = (url: string): string => url.replace(/\/$/, "");

export class DifyGateway {
  constructor(private readonly config: DifyGatewayConfig) {}

  async getRuntimeBotConfig(botId: string, token?: string): Promise<RuntimeBotConfig> {
    const base = cleanBaseUrl(this.config.consoleApiBaseUrl);
    const url = new URL(`${base}/workspaces/current/channel-integrations/runtime/bots/${encodeURIComponent(botId)}`);
    if (token) url.searchParams.set("token", token);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`load channel integration runtime config failed: ${response.status} ${await response.text()}`);
    }
    return response.json() as Promise<RuntimeBotConfig>;
  }

  async markVerified(botId: string, token?: string): Promise<void> {
    const base = cleanBaseUrl(this.config.consoleApiBaseUrl);
    const url = new URL(`${base}/workspaces/current/channel-integrations/runtime/bots/${encodeURIComponent(botId)}/verified`);
    if (token) url.searchParams.set("token", token);
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) {
      throw new Error(`mark channel integration verified failed: ${response.status} ${await response.text()}`);
    }
  }

  async chat(apiKey: string, query: string, user: string): Promise<string> {
    const client = new ChatClient({ apiKey, baseUrl: this.config.baseUrl, timeout: 120, maxRetries: 1 });
    const response = await client.createChatMessage({ inputs: {}, query, user, response_mode: "blocking" });
    return answerFromResponse(response.data as JsonObject);
  }
}
