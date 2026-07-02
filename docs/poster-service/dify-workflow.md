# Dify 发布海报工作流接入说明

## 应用形态

- Dify 应用类型：聊天工作流或 Agent 工作流。
- LLM 模型：所有意图解析、文案整理、提示词优化节点统一配置为 `gpt-5.5`。
- 工具：导入 `deploy/poster-service/openapi-dify.yaml`，操作名 `generatePoster`。

## 生产 v1 节点

1. 开始节点接收用户输入：主题、背景、节日元素、目标人群、文案偏好。
2. Code 节点扩展素材检索词，例如把“啤酒”补充为“鲜啤、瞢瞢熊鲜啤交易所、门店、品牌视觉素材”。
3. 知识库检索节点默认检索 `MMB统一材料知识库-图文结构化验证`，把命中的素材说明传给 LLM 和 poster-service。
4. LLM 节点用 `gpt-5.5` 输出一段优化后的生图提示词正文，不输出 JSON。
5. Code 节点组装 poster-service 请求，传 `overlay_text=false`，避免程序叠字、黑框和“发布海报”硬编码。
6. HTTP/OpenAPI 节点调用 `generatePoster`，默认尺寸 `1080x1440`。
7. Code/回答节点先返回“优化后的生图提示词”，再用 Markdown 展示图片和原图链接。

## poster-service 请求示例

```json
{
  "brief": {
    "theme": "端午节啤酒促销",
    "background": "GPT-5.5 优化后的完整中文生图提示词",
    "special_elements": [],
    "audience": "朋友圈/小红书用户",
    "main_title": null,
    "subtitle": null,
    "selling_points": [],
    "brand_constraints": "参考知识库素材的品牌、产品、色彩和风格；不要在图片中生成可读文字、Logo、价格或水印。"
  },
  "assets": [
    {
      "title": "知识库素材 1",
      "description": "素材 Caption、标签、文件名和预览路径摘要",
      "url": "可选素材 URL",
      "tags": ["门店效果图", "品牌视觉素材"]
    }
  ],
  "size": "1080x1440",
  "overlay_text": false
}
```

## 生产验证记录

- `poster-service /health`：`openai_configured=true`，`llm_model=gpt-5.5`，`image_mode=responses`。
- 用例 `新品发布，科技感背景，突出预约试用`：返回优化提示词 + Markdown 图片；图片无“发布海报”硬编码和程序叠字黑框。
- 用例 `端午节啤酒促销，清爽绿色背景，加粽子和麦芽元素`：返回优化提示词 + Markdown 图片；命中图文验证库素材 5 条，并在提示词中引用“瞢瞢熊鲜啤交易所”等素材信息。
