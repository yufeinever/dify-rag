export type Intent = "chat" | "copywriting" | "poster";

const posterWords = ["海报", "宣传图", "配图", "生图", "生成图", "图片", "封面", "主视觉"];
const copyWords = ["文案", "朋友圈", "小红书", "推广语", "宣传语", "广告语", "推文", "标题", "slogan", "Slogan"];

export const detectIntent = (text: string): Intent => {
  const normalized = text.trim();
  if (posterWords.some((word) => normalized.includes(word))) return "poster";
  if (copyWords.some((word) => normalized.includes(word))) return "copywriting";
  return "chat";
};

export const buildCopywritingPrompt = (text: string): string => `请作为 MMB 的品牌营销文案助手，基于 MMB 内部资料和你的专业判断，生成可以直接用于朋友圈、小红书、社群或门店活动的中文文案。要求：先给 1 个推荐版本，再给 2 个备选版本；语言自然，不夸大无法证实的事实；如涉及 MMB 事实请先查内部材料。用户需求：${text}`;
