import assert from "node:assert/strict";
import http from "node:http";
import { afterEach, describe, it } from "node:test";
import { createApp } from "../src/app.ts";
import type { RuntimeBotConfig } from "../src/difyGateway.ts";

const originalFetch = globalThis.fetch;

const runtimeConfig = (enabled = true): RuntimeBotConfig => ({
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  name: "MMBAI",
  channel: "feishu",
  enabled,
  app_id: "cli_xxx",
  app_secret: "app_secret",
  verification_token: "verify_token",
  encrypt_key: "encrypt_key_12345678901234567890123456789012",
  bot_name: "MMBAI",
  bot_open_id: "ou_bot",
  bindings: {},
});

const installRuntimeFetch = (runtime: RuntimeBotConfig, calls: string[]) => {
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    calls.push(`${init?.method ?? "GET"} ${url}`);
    if (url.startsWith("http://dify-console/console/api/workspaces/current/channel-integrations/runtime/bots/")) {
      return new Response(JSON.stringify(runtime), { status: 200, headers: { "content-type": "application/json" } });
    }
    return new Response("not found", { status: 404 });
  }) as typeof fetch;
};

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("feishu bot app", () => {
  it("loads runtime config by bot id and answers URL verification", async () => {
    process.env.DIFY_CONSOLE_API_BASE_URL = "http://dify-console/console/api";
    const calls: string[] = [];
    installRuntimeFetch(runtimeConfig(), calls);
    const response = await postJson("/feishu-bot/events/11111111-1111-1111-1111-111111111111?token=callback_token", {
      type: "url_verification",
      token: "verify_token",
      challenge: "challenge-value",
    });
    assert.equal(response.status, 200);
    assert.deepEqual(response.body, { challenge: "challenge-value" });
    assert.equal(calls.some(call => call.includes("token=callback_token")), true);
    assert.equal(calls.some(call => call.startsWith("POST ") && call.includes("/verified")), true);
  });

  it("ignores disabled bots after token validation", async () => {
    process.env.DIFY_CONSOLE_API_BASE_URL = "http://dify-console/console/api";
    const calls: string[] = [];
    installRuntimeFetch(runtimeConfig(false), calls);
    const response = await postJson("/feishu-bot/events/11111111-1111-1111-1111-111111111111?token=callback_token", {
      header: { token: "verify_token", event_type: "im.message.receive_v1" },
      event: {
        sender: { sender_id: { open_id: "ou_user" } },
        message: {
          message_id: "om_1",
          chat_id: "oc_1",
          chat_type: "p2p",
          message_type: "text",
          content: JSON.stringify({ text: "hello" }),
        },
      },
    });
    assert.equal(response.status, 200);
    assert.deepEqual(response.body, { ignored: true, reason: "bot disabled" });
  });
});

const postJson = async (path: string, body: unknown): Promise<{ status: number; body: unknown }> => {
  const app = createApp();
  const server = app.listen(0);
  try {
    const address = server.address();
    assert.equal(typeof address, "object");
    assert(address);
    const port = address.port;
    return await new Promise((resolve, reject) => {
      const payload = JSON.stringify(body);
      const request = http.request({
        hostname: "127.0.0.1",
        port,
        path,
        method: "POST",
        headers: {
          "content-type": "application/json",
          "content-length": Buffer.byteLength(payload),
        },
      }, (response) => {
        const chunks: Buffer[] = [];
        response.on("data", chunk => chunks.push(Buffer.from(chunk)));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          resolve({ status: response.statusCode ?? 0, body: text ? JSON.parse(text) : null });
        });
      });
      request.on("error", reject);
      request.end(payload);
    });
  } finally {
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
};
