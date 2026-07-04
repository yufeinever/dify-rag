import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { RuntimeBotConfig } from "../src/difyGateway.ts";
import { selectMessageRoute } from "../src/routing.ts";

const runtime = (bindings: RuntimeBotConfig["bindings"]): RuntimeBotConfig => ({
  id: "11111111-1111-1111-1111-111111111111",
  tenant_id: "22222222-2222-2222-2222-222222222222",
  name: "MMBAI",
  channel: "feishu",
  enabled: true,
  app_id: "cli_xxx",
  app_secret: "app_secret",
  verification_token: "verify_token",
  encrypt_key: "encrypt_key_12345678901234567890123456789012",
  bindings,
});

const defaultBinding = { app_id: "app-default", app_name: "主入口", api_key: "default-key" };
const copywritingBinding = { app_id: "app-copy", app_name: "文案", api_key: "copy-key" };
const posterBinding = { app_id: "app-poster", app_name: "海报", api_key: "poster-key" };

describe("selectMessageRoute", () => {
  it("routes ordinary chat to the primary Dify app", () => {
    const route = selectMessageRoute("MMB 是什么？", runtime({ default: defaultBinding }));
    assert.equal(route.kind, "dify");
    assert.equal(route.kind === "dify" ? route.binding?.api_key : undefined, "default-key");
  });

  it("does not intercept copywriting without an explicit override", () => {
    const route = selectMessageRoute("帮我写一段小红书文案", runtime({ default: defaultBinding }));
    assert.equal(route.kind, "dify");
    assert.equal(route.kind === "dify" ? route.binding?.api_key : undefined, "default-key");
  });

  it("routes copywriting to the override app when configured", () => {
    const route = selectMessageRoute("帮我写一段小红书文案", runtime({ default: defaultBinding, copywriting: copywritingBinding }));
    assert.equal(route.kind, "dify");
    assert.equal(route.kind === "dify" ? route.binding?.api_key : undefined, "copy-key");
  });

  it("does not intercept poster requests without an explicit poster override", () => {
    const route = selectMessageRoute("帮我生成一张海报", runtime({ default: defaultBinding }));
    assert.equal(route.kind, "dify");
    assert.equal(route.kind === "dify" ? route.binding?.api_key : undefined, "default-key");
  });

  it("routes poster requests to poster-service when the override is configured", () => {
    const route = selectMessageRoute("帮我生成一张海报", runtime({ default: defaultBinding, poster: posterBinding }));
    assert.equal(route.kind, "poster-service");
  });
});
