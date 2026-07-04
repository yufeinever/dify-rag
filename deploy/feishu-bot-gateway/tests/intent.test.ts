import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { detectOverrideIntent } from "../src/intent.ts";

describe("detectOverrideIntent", () => {
  it("detects poster override requests", () => {
    assert.equal(detectOverrideIntent("帮我生成一张端午节海报"), "poster");
  });

  it("detects copywriting override requests", () => {
    assert.equal(detectOverrideIntent("写一段小红书文案"), "copywriting");
  });

  it("does not classify ordinary chat", () => {
    assert.equal(detectOverrideIntent("MMB 是什么？"), null);
  });
});
