import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import * as lark from "@larksuiteoapi/node-sdk";

export class FeishuClient {
  private readonly client: any;

  constructor(appId: string, appSecret: string) {
    this.client = new lark.Client({ appId, appSecret, disableTokenCache: false });
  }

  async sendText(chatId: string, text: string): Promise<void> {
    await this.client.im.message.create({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: chatId,
        msg_type: "text",
        content: JSON.stringify({ text: trimForFeishu(text) }),
      },
    });
  }

  async sendImageFromUrl(chatId: string, imageUrl: string): Promise<void> {
    const filePath = await downloadToTempFile(imageUrl);
    try {
      const upload = await this.client.im.image.create({
        data: {
          image_type: "message",
          image: fs.createReadStream(filePath),
        },
      });
      const imageKey = upload?.data?.image_key;
      if (!imageKey) throw new Error("Feishu image upload did not return image_key");
      await this.client.im.message.create({
        params: { receive_id_type: "chat_id" },
        data: {
          receive_id: chatId,
          msg_type: "image",
          content: JSON.stringify({ image_key: imageKey }),
        },
      });
    } finally {
      fs.promises.unlink(filePath).catch(() => undefined);
    }
  }
}

const trimForFeishu = (text: string): string => {
  const normalized = text.trim() || "我没有生成有效回复。";
  return normalized.length > 14_000 ? `${normalized.slice(0, 14_000)}\n\n[内容过长，已截断]` : normalized;
};

const downloadToTempFile = async (url: string): Promise<string> => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`download image failed: ${response.status}`);
  const contentType = response.headers.get("content-type") ?? "";
  const suffix = contentType.includes("jpeg") ? ".jpg" : ".png";
  const filePath = path.join(os.tmpdir(), `feishu-poster-${Date.now()}-${Math.random().toString(16).slice(2)}${suffix}`);
  const buffer = Buffer.from(await response.arrayBuffer());
  await fs.promises.writeFile(filePath, buffer);
  return filePath;
};
