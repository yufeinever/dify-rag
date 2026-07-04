import type { RuntimeAppBinding, RuntimeBotConfig } from "./difyGateway.js";
import { detectOverrideIntent } from "./intent.js";

export type MessageRoute = {
  kind: "dify";
  binding?: RuntimeAppBinding;
  overrideIntent: ReturnType<typeof detectOverrideIntent>;
} | {
  kind: "poster-service";
  overrideIntent: "poster";
};

export const selectMessageRoute = (text: string, runtime: RuntimeBotConfig): MessageRoute => {
  const overrideIntent = detectOverrideIntent(text);
  if (overrideIntent === "poster" && runtime.bindings.poster) {
    return { kind: "poster-service", overrideIntent };
  }
  if (overrideIntent === "copywriting" && runtime.bindings.copywriting?.api_key) {
    return { kind: "dify", binding: runtime.bindings.copywriting, overrideIntent };
  }
  return { kind: "dify", binding: runtime.bindings.default, overrideIntent };
};
