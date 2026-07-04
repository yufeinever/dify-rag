export class TtlSet {
  private readonly seen = new Map<string, number>();

  constructor(private readonly ttlMs: number) {}

  add(key: string, now = Date.now()): boolean {
    this.cleanup(now);
    if (this.seen.has(key)) return false;
    this.seen.set(key, now + this.ttlMs);
    return true;
  }

  has(key: string, now = Date.now()): boolean {
    this.cleanup(now);
    return this.seen.has(key);
  }

  cleanup(now = Date.now()): void {
    for (const [key, expiresAt] of this.seen.entries()) {
      if (expiresAt <= now) this.seen.delete(key);
    }
  }
}

export class SlidingWindowRateLimiter {
  private readonly buckets = new Map<string, number[]>();

  constructor(
    private readonly windowMs: number,
    private readonly maxMessages: number,
  ) {}

  take(key: string, now = Date.now()): boolean {
    const cutoff = now - this.windowMs;
    const bucket = (this.buckets.get(key) ?? []).filter((time) => time > cutoff);
    if (bucket.length >= this.maxMessages) {
      this.buckets.set(key, bucket);
      return false;
    }
    bucket.push(now);
    this.buckets.set(key, bucket);
    return true;
  }
}
