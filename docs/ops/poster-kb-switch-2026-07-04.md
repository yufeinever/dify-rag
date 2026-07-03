# Poster Assistant Knowledge Base Switch

Date: 2026-07-04 Asia/Shanghai

## Change

Switched the poster assistant chain from `MMB统一材料知识库-V2` to `MMB统一材料知识库-v4.1-一次导入增强` in production.

Old dataset:

- Name: `MMB统一材料知识库-V2`
- ID: `796c7318-7637-4716-b2d6-ac046c4274f1`

New dataset:

- Name: `MMB统一材料知识库-v4.1-一次导入增强`
- ID: `29f282db-a0c7-4f9b-a360-fdb921d53948`

Updated apps:

- `发布海报助手`
  - App ID: `7bdc02f9-388b-4e9a-8191-9ca812528bdf`
  - Installed App ID: `28a67138-2f09-4e1a-894c-745b0f1c0546`
  - Updated `app_dataset_joins` from V2 to V4.1.
  - Updated workflow graph dataset references in draft and published workflow versions.
- `发布海报助手-后台生成`
  - App ID: `13f7a06c-769d-474c-8863-613e9aeb25cb`
  - Installed App ID: `ce20b86c-9a3c-44f2-8dd9-7fa182f85f05`
  - Updated workflow graph dataset references in draft and published workflow versions.

Affected workflow rows: 5.

## Before/After Test

Test query:

```text
请生成一张深圳文交所与MMB战略合作宣传海报，突出橙色熊IP、MMB Logo、合作官宣，不要包含二维码。
```

Before switch, the live `发布海报助手` run used V2 vector index `Vector_index_796c7318_7637_4716_b2d6_ac046c4274f1_Node` and generated:

- Image: `http://150.5.132.104:8088/files/poster-87740d13-f607-46be-8ec1-dcfb91c2acbb.png`
- Referenced knowledge materials: 6
- Message ID: `da4dbac3-e12b-40cc-9fe4-ede4aed0b52d`

After switch, the live `发布海报助手` run used V4.1 vector index `Vector_index_f09dd86b_c92a_43ba_ab4a_209c6dcf807a_Node` and generated:

- Image: `http://150.5.132.104:8088/files/poster-38525147-3425-4391-adbe-d089ecb39814.png`
- Referenced knowledge materials: 5
- Message ID: `ae11f3cd-9806-4a9a-bcf5-5d342dbdf553`

After switch, `发布海报助手-后台生成` also used V4.1 and submitted an async poster job successfully:

- Job ID: `c94f932e-b4af-4f18-870f-929ce64f00a3`
- Message ID: `8fbfa042-c76a-4678-b718-de8a56e1347d`

## Retrieval Observations

Before switch, V2 was strong for pure visual retrieval:

- `深圳文交所和MMB战略合作海报` retrieved the exact cooperation poster and cooperation logo assets.
- `MMB Logo 和熊IP是什么样` retrieved `MMB啤酒熊品牌Logo.png` as top result.

V2 was weak for business-poster queries:

- `MMB加盟方式有哪些，生成招商海报需要哪些卖点` still mostly retrieved logo/cooperation visual snippets rather than franchise facts.

V4.1 improves typed and source-bound context:

- Strategic-cooperation queries retrieve typed `business_fact` summaries plus image-derived visual context.
- Business facts are cleaner and safer for answer/prompt grounding than V2's untyped snippets.

Known caveat:

- For pure Logo/IP visual questions, V2's visual-material recall is more direct. V4.1 can still retrieve the assets, but the poster workflow may need a follow-up query/filter refinement if visual-only prompt quality becomes worse.

## Post-change Reference Check

After the switch, V2 had no remaining app/workflow references in production. V4.1 is now referenced by:

- `MMB业务助手-v4.1`
- `发布海报助手`
- `发布海报助手-后台生成`

## Rollback

Rollback is a direct dataset ID replacement:

- Replace `29f282db-a0c7-4f9b-a360-fdb921d53948` with `796c7318-7637-4716-b2d6-ac046c4274f1` in the two poster apps' workflow graphs.
- Restore `发布海报助手` `app_dataset_joins.dataset_id` to `796c7318-7637-4716-b2d6-ac046c4274f1`.
