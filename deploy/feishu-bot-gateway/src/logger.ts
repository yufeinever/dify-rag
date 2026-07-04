export type Logger = {
  info: (message: string, meta?: Record<string, unknown>) => void;
  warn: (message: string, meta?: Record<string, unknown>) => void;
  error: (message: string, meta?: Record<string, unknown>) => void;
  debug: (message: string, meta?: Record<string, unknown>) => void;
};

const line = (level: string, message: string, meta?: Record<string, unknown>): void => {
  const payload = meta && Object.keys(meta).length > 0 ? ` ${JSON.stringify(meta)}` : "";
  // Keep logs single-line for docker log scanners.
  console.log(`${new Date().toISOString()} ${level.toUpperCase()} ${message}${payload}`);
};

export const createLogger = (level: string): Logger => {
  const debugEnabled = level === "debug";
  return {
    info: (message, meta) => line("info", message, meta),
    warn: (message, meta) => line("warn", message, meta),
    error: (message, meta) => line("error", message, meta),
    debug: (message, meta) => {
      if (debugEnabled) line("debug", message, meta);
    },
  };
};
