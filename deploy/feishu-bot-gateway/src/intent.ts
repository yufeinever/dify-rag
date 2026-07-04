export type OverrideIntent = "copywriting" | "poster" | null;

const posterWords = ["海报", "宣传图", "配图", "生图", "生成图", "图片", "封面", "主视觉"];
const copyWords = ["文案", "朋友圈", "小红书", "推广语", "宣传语", "广告语", "推文", "标题", "slogan", "Slogan"];

export const detectOverrideIntent = (text: string): OverrideIntent => {
  const normalized = text.trim();
  if (posterWords.some((word) => normalized.includes(word))) return "poster";
  if (copyWords.some((word) => normalized.includes(word))) return "copywriting";
  return null;
};
