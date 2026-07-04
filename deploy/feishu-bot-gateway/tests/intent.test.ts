import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { detectIntent, buildCopywritingPrompt } from "../src/intent.ts";

describe("detectIntent", () => {
  it("detects poster requests", () => {
    assert.equal(detectIntent("帮我生成一张端午节海报"), "poster");
  });

  it("detects copywriting requests", () => {
    assert.equal(detectIntent("写一段小红书文案"), "copywriting");
  });

  it("falls back to chat", () => {
    assert.equal(detectIntent("MMB 是什么？"), "chat");
  });
});

describe("buildCopywritingPrompt", () => {
  it("keeps the user request and adds marketing constraints", () => {
    const prompt = buildCopywritingPrompt("新品活动");
    assert.match(prompt, /新品活动/);
    assert.match(prompt, /MMB/);
    assert.match(prompt, /小红书/);
  });
});
