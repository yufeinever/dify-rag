# MMB Campaign Copywriting Skill

Use this skill for social posts, Xiaohongshu, WeChat Moments, group announcements, sales scripts, short campaign copy, and customer-facing explanations.

Workflow:
1. Decide whether enterprise facts are required. If yes, call `search_mmb_context` first.
2. For normal short copy, use GPT-5.5 native writing ability with retrieved MMB evidence.
3. Call `create_campaign_copy` only when a dedicated MMB copywriting workflow is needed; if it returns `not_configured`, continue drafting directly in chat.
4. Keep copy direct, compliant, and usable. Avoid unsupported claims, medical/financial promises, and fake pricing.
5. Offer 2-3 variants only when variants help the user choose a tone or platform.
