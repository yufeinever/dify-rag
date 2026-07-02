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

## MMB 小熊默认规则

- `GPT-5.5 优化生图提示词` 节点默认要求：如果用户没有明确强调不需要小熊形象，则使用 MMB 小熊形象作为品牌 IP 元素。
- 小熊应自然融入画面，默认放在角落、前景侧边或互动区域，不抢主视觉。
- 动作由主题自动适配：促销场景招手或举牌，啤酒场景举杯，节日场景庆祝，新品发布场景指向产品或预约入口。
- 当用户明确说不要小熊、不要 IP、不要卡通形象、纯产品图、纯背景图或纯商务风时，提示词必须排除小熊/IP/卡通/吉祥物元素。
- `组装生图请求` Code 节点在未排除小熊时默认追加参考资产：`瞢瞢熊IP形象-捂嘴表情.png`。
- 默认参考资产预览路径：`/files/872f19ba-fe02-47a1-97e2-097cc64c7d45/image-preview`。
- 追加后节点会输出 `default_bear_asset_added=true`；明确排除时输出 `exclude_bear=true` 且不追加该默认资产。

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
    },
    {
      "title": "瞢瞢熊IP形象-捂嘴表情.png",
      "description": "MMB 小熊品牌 IP 默认参考图。用户没有明确排除小熊/IP/卡通形象时，用作海报里的品牌角色参考。",
      "url": "/files/872f19ba-fe02-47a1-97e2-097cc64c7d45/image-preview",
      "tags": ["MMB", "小熊", "品牌IP", "默认参考图"],
      "source": "default_mmb_bear"
    }
  ],
  "size": "1080x1440",
  "overlay_text": false
}
```


## HTTP 节点超时配置

- `调用 GPT-5.5 生图服务` HTTP 节点显式设置 `timeout.connect=10`、`timeout.read=480`、`timeout.write=60`。
- 关闭该 HTTP 节点重试：`retry_enabled=false`、`max_retries=0`。生图请求可能超过 2 分钟，如果 Dify 先超时但 poster-service 后台仍在生成，重试会造成重复生图。
- 2026-07-02 验证：`节日活动海报，温暖氛围，突出品牌和限时优惠` 在超时配置更新后成功返回优化提示词和图片，HTTP 节点 `status=succeeded`。

## 生产验证记录

- `poster-service /health`：`openai_configured=true`，`llm_model=gpt-5.5`，`image_mode=responses`。
- 用例 `新品发布，科技感背景，突出预约试用`：返回优化提示词 + Markdown 图片；图片无“发布海报”硬编码和程序叠字黑框。
- 用例 `端午节啤酒促销，清爽绿色背景，加粽子和麦芽元素`：返回优化提示词 + Markdown 图片；命中图文验证库素材 5 条，并在提示词中引用“瞢瞢熊鲜啤交易所”等素材信息。
- 2026-07-02 小熊默认规则验证：`端午节啤酒促销，清爽绿色背景，加粽子和麦芽元素` 返回提示词包含 MMB 小熊举杯/庆祝动作，`asset_count=6`，`default_bear_asset_added=true`，payload 包含默认小熊预览路径。
- 2026-07-02 小熊默认规则验证：`新品发布，科技感背景，突出预约试用` 返回提示词包含 MMB 小熊指向预约入口/互动装置，`asset_count=6`，`default_bear_asset_added=true`。
- 2026-07-02 排除规则验证：`新品发布，科技感背景，不要小熊形象` 返回提示词明确排除小熊/IP/卡通/吉祥物，`asset_count=5`，`exclude_bear=true`，payload 不含默认小熊预览路径。

