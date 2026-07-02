# Dify 发布海报工作流接入说明

## 应用形态

- Dify 应用类型：聊天工作流或 Agent 工作流。
- LLM 模型：所有意图解析、文案整理、提示词优化节点统一配置为 `gpt-5.5`。
- 工具：导入 `deploy/poster-service/openapi-dify.yaml`，操作名 `generatePoster`。

## 推荐节点

1. 开始节点接收用户输入：主题、背景、节日元素、目标人群、文案偏好。
2. LLM 节点用 `gpt-5.5` 输出 JSON brief，字段包括 `theme`、`background`、`special_elements`、`audience`、`main_title`、`subtitle`、`selling_points`、`brand_constraints`。
3. 知识库检索节点检索生产素材库图片说明，整理为 `assets` 数组：`url`、`title`、`description`、`tags`。
4. OpenAPI 工具节点调用 `generatePoster`，默认传 `size=1080x1440`、`overlay_text=true`。
5. 回答节点返回 `poster_url` 和 `thumbnail_url`，如果 `status=failed`，返回 `error` 并提示用户调整需求或联系管理员检查 OpenAI 配置。

## Brief JSON 示例

```json
{
  "brief": {
    "theme": "端午节啤酒促销",
    "background": "清爽绿色、冰镇啤酒、节日氛围",
    "special_elements": ["粽子", "麦穗", "水珠"],
    "audience": "城市年轻消费者",
    "main_title": "端午清爽开饮",
    "subtitle": "限时组合优惠",
    "selling_points": ["精选麦芽", "冰镇畅饮", "扫码预约"],
    "brand_constraints": "保持品牌色，避免夸张医疗或功效表述"
  },
  "assets": [],
  "size": "1080x1440",
  "overlay_text": true
}
```
