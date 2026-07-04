import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { extractMessageEvent, stripBotMention } from "../src/feishuEvent.ts";

describe("stripBotMention", () => {
  it("removes xml-style Feishu at mention", () => {
    assert.equal(stripBotMention('<at user_id="ou_bot">MMBAI</at> 写文案', "MMBAI"), "写文案");
  });
});

describe("extractMessageEvent", () => {
  it("extracts private text events", () => {
    const event = extractMessageEvent({
      header: { event_id: "evt", event_type: "im.message.receive_v1" },
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
    }, { botName: "MMBAI" });
    assert.equal(event?.text, "hello");
    assert.equal(event?.mentionedBot, true);
  });

  it("marks group events without mentions as not mentioned", () => {
    const event = extractMessageEvent({
      header: { event_id: "evt", event_type: "im.message.receive_v1" },
      event: {
        sender: { sender_id: { open_id: "ou_user" } },
        message: {
          message_id: "om_2",
          chat_id: "oc_2",
          chat_type: "group",
          message_type: "text",
          content: JSON.stringify({ text: "hello" }),
          mentions: [],
        },
      },
    }, { botName: "MMBAI" });
    assert.equal(event?.mentionedBot, false);
  });
});
