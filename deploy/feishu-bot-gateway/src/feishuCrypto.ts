import crypto from "node:crypto";

export const decryptFeishuPayload = (encryptKey: string, encrypted: string): unknown => {
  const key = crypto.createHash("sha256").update(encryptKey).digest();
  const encryptedBuffer = Buffer.from(encrypted, "base64");
  if (encryptedBuffer.length <= 16) {
    throw new Error("Invalid encrypted Feishu payload");
  }
  const iv = encryptedBuffer.subarray(0, 16);
  const cipherText = encryptedBuffer.subarray(16);
  const decipher = crypto.createDecipheriv("aes-256-cbc", key, iv);
  decipher.setAutoPadding(true);
  const decrypted = Buffer.concat([decipher.update(cipherText), decipher.final()]).toString("utf8");
  return JSON.parse(decrypted);
};

export const verifyFeishuSignature = (params: {
  encryptKey: string;
  timestamp?: string | string[];
  nonce?: string | string[];
  signature?: string | string[];
  body: string;
}): boolean => {
  const timestamp = Array.isArray(params.timestamp) ? params.timestamp[0] : params.timestamp;
  const nonce = Array.isArray(params.nonce) ? params.nonce[0] : params.nonce;
  const signature = Array.isArray(params.signature) ? params.signature[0] : params.signature;
  if (!timestamp || !nonce || !signature) return false;

  const base = `${timestamp}${nonce}${params.encryptKey}${params.body}`;
  const expected = crypto.createHash("sha256").update(base).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
};
