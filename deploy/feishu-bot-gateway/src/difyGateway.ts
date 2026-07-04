import { ChatClient } from "../../../sdks/nodejs-client/dist/index.mjs";
import type { JsonObject } from "../../../sdks/nodejs-client/dist/index.mjs";

export type DifyGatewayConfig = {
  baseUrl: string;
  advisorApiKey: string;
  copywritingApiKey?: string;
};

const answerFromResponse = (data: JsonObject): string => {
  const answer = data.answer;
  if (typeof answer === "string" && answer.trim()) return answer;
  const text = data.text;
  if (typeof text === "string" && text.trim()) return text;
  return JSON.stringify(data, null, 2);
};

export class DifyGateway {
  private readonly advisor: ChatClient;
  private readonly copywriting: ChatClient;

  constructor(config: DifyGatewayConfig) {
    this.advisor = new ChatClient({ apiKey: config.advisorApiKey, baseUrl: config.baseUrl, timeout: 120, maxRetries: 1 });
    this.copywriting = new ChatClient({ apiKey: config.copywritingApiKey ?? config.advisorApiKey, baseUrl: config.baseUrl, timeout: 120, maxRetries: 1 });
  }

  async chat(query: string, user: string): Promise<string> {
    const response = await this.advisor.createChatMessage({ inputs: {}, query, user, response_mode: "blocking" });
    return answerFromResponse(response.data as JsonObject);
  }

  async copywrite(query: string, user: string): Promise<string> {
    const response = await this.copywriting.createChatMessage({ inputs: {}, query, user, response_mode: "blocking" });
    return answerFromResponse(response.data as JsonObject);
  }
}
