import process from "node:process";

export type GatewayConfig = {
  port: number;
  publicBaseUrl?: string;
  dify: {
    baseUrl: string;
    consoleApiBaseUrl: string;
  };
  poster: {
    serviceUrl: string;
    pollIntervalMs: number;
    pollTimeoutMs: number;
    size: string;
  };
  idempotencyTtlMs: number;
  rateLimitWindowMs: number;
  rateLimitMaxMessages: number;
  runtimeConfigCacheTtlMs: number;
  logLevel: string;
};

const optional = (name: string): string | undefined => {
  const value = process.env[name];
  return value && value.trim() ? value.trim() : undefined;
};

const intEnv = (name: string, fallback: number): number => {
  const value = optional(name);
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${name} must be a positive integer`);
  }
  return parsed;
};

export const loadConfig = (): GatewayConfig => ({
  port: intEnv("PORT", 8096),
  publicBaseUrl: optional("PUBLIC_BASE_URL"),
  dify: {
    baseUrl: optional("DIFY_BASE_URL") ?? "http://nginx/v1",
    consoleApiBaseUrl: optional("DIFY_CONSOLE_API_BASE_URL") ?? "http://nginx/console/api",
  },
  poster: {
    serviceUrl: optional("POSTER_SERVICE_URL") ?? "http://poster-service:8088",
    pollIntervalMs: intEnv("POSTER_POLL_INTERVAL_MS", 15_000),
    pollTimeoutMs: intEnv("POSTER_POLL_TIMEOUT_MS", 900_000),
    size: optional("POSTER_SIZE") ?? "1080x1440",
  },
  idempotencyTtlMs: intEnv("IDEMPOTENCY_TTL_MS", 600_000),
  rateLimitWindowMs: intEnv("RATE_LIMIT_WINDOW_MS", 60_000),
  rateLimitMaxMessages: intEnv("RATE_LIMIT_MAX_MESSAGES", 12),
  runtimeConfigCacheTtlMs: intEnv("RUNTIME_CONFIG_CACHE_TTL_MS", 30_000),
  logLevel: optional("LOG_LEVEL") ?? "info",
});
