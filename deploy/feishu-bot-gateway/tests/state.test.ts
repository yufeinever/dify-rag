import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { SlidingWindowRateLimiter, TtlSet } from "../src/state.ts";

describe("TtlSet", () => {
  it("rejects duplicate keys until ttl expires", () => {
    const set = new TtlSet(100);
    assert.equal(set.add("m", 1000), true);
    assert.equal(set.add("m", 1050), false);
    assert.equal(set.add("m", 1200), true);
  });
});

describe("SlidingWindowRateLimiter", () => {
  it("limits messages per window", () => {
    const limiter = new SlidingWindowRateLimiter(100, 2);
    assert.equal(limiter.take("u", 1000), true);
    assert.equal(limiter.take("u", 1010), true);
    assert.equal(limiter.take("u", 1020), false);
    assert.equal(limiter.take("u", 1200), true);
  });
});
