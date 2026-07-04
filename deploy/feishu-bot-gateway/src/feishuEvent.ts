import { randomUUID } from "node:crypto";

export type FeishuMessageEvent = {
  eventId: string;
  messageId: string;
  chatId: string;
  chatType: "p2p" | "group" | string;
  senderOpenId: string;
  messageType: string;
  text: string;
  mentionedBot: boolean;
};

type RawEvent = Record<string, any>;

const parseTextContent = (content: unknown): string => {
  if (typeof content !== "string") return "";
  try {
    const parsed = JSON.parse(content) as { text?: unknown };
    return typeof parsed.text === "string" ? parsed.text : "";
  } catch {
    return content;
  }
};

export const stripBotMention = (text: string, botName: string): string => {
  const escapedBotName = botName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return text
    .replace(/<at\s+[^>]*>.*?<\/at>/g, "")
    .replace(new RegExp(`@${escapedBotName}`, "g"), "")
    .trim();
};

const isBotMentioned = (mentions: unknown, botOpenId?: string, botName?: string): boolean => {
  if (!Array.isArray(mentions)) return false;
  if (mentions.length === 0) return false;
  if (!botOpenId && !botName) return true;
  return mentions.some((mention) => {
    const item = mention as Record<string, any>;
    const id = item.id ?? item.open_id ?? item.user_id ?? item.tenant_key;
    const name = item.name ?? item.key;
    return (botOpenId && id === botOpenId) || (botName && name === botName);
  });
};

export const extractMessageEvent = (
  payload: RawEvent,
  options: { botOpenId?: string; botName: string },
): FeishuMessageEvent | null => {
  const header = payload.header ?? {};
  const event = payload.event ?? payload;
  const eventType = header.event_type ?? payload.type;
  if (typeof eventType === "string" && !eventType.includes("message")) return null;

  const message = event.message;
  if (!message) return null;

  const chatType = message.chat_type ?? message.chatType ?? "";
  const rawText = parseTextContent(message.content);
  const text = stripBotMention(rawText, options.botName);
  const senderOpenId = event.sender?.sender_id?.open_id ?? event.sender?.open_id ?? "unknown";
  const mentionedBot = chatType === "p2p" || isBotMentioned(message.mentions, options.botOpenId, options.botName);

  return {
    eventId: header.event_id ?? message.message_id ?? randomUUID(),
    messageId: message.message_id,
    chatId: message.chat_id,
    chatType,
    senderOpenId,
    messageType: message.message_type ?? "unknown",
    text,
    mentionedBot,
  };
};
