# MMB Capability Center

`mmb-capability-center` 是 MMBAI 企业知识库与能力中台的第一阶段实现。它不做飞书协议，也不做大模型意图识别；它把企业知识、素材、文案、海报、团队产物和审计封装成稳定工具 API，供 Dify Agent、Hermes 或其他主 Agent 调用。

## 职责边界

- Channel Gateway：飞书/企业微信/Web 协议、验签、群聊 @、私聊、消息回发、图片上传、幂等和限流。
- 主入口 Agent：理解用户意图，决定调用知识检索、素材检索、文案、海报或团队产物工具。
- Capability Center：执行工具、隔离会话、保存审计、统一持有 Dify/material/poster 服务密钥。

## 会话模型

- 私聊：`tenant_id + bot_id + channel + p2p + open_id`
- 群聊共享：`tenant_id + bot_id + channel + group + chat_id`
- 群聊个人上下文：`tenant_id + bot_id + channel + group-user + chat_id + sender_open_id`

默认不会把 A 员工私聊上下文写入 B 员工或群聊上下文。群聊产物只有显式调用 `create_team_artifact` 才会进入团队或项目资产。

## 工具 API

- HTTP/OpenAPI 工具保留 `search_enterprise_knowledge`、`read_knowledge`、`search_materials`、`read_material`、`generate_copywriting`、`create_business_artifact`、`create_poster_job`、`create_team_artifact`。
- MCP 入口为 `POST /mcp`，面向 Hermes 暴露通用原语：`search_knowledge`、`read_knowledge`、`search_materials`、`read_material`、`create_artifact`、`create_poster_job`、`save_team_asset`。
- Hermes 主 Agent 不直接看到 Dify 底层 `list_documents`、`read_chunks`、旧 Office 单项工具；这些能力由 Capability Center 内部封装。

`GET /openapi-dify.yaml` 可作为 Dify OpenAPI 工具导入规范。

## 配置

复制 `.env.example` 为 `.env`，按环境填写：

```env
CAPABILITY_AUTH_TOKEN=
MATERIAL_CATALOG_URL=http://material-catalog-service:8091
POSTER_SERVICE_URL=http://poster-service:8088
DIFY_BASE_URL=http://nginx/v1
DIFY_DEFAULT_APP_API_KEY=
DIFY_COPYWRITING_APP_API_KEY=
DIFY_BUSINESS_ARTIFACT_APP_API_KEY=
```

`CAPABILITY_AUTH_TOKEN` 设置后，所有 `/v1/*` 和 `/mcp` 接口都要求 `Authorization: Bearer <token>`。服务端密钥不进入 Agent 提示词。

Hermes MCP 配置示例：

```yaml
mcp_servers:
  mmb_capability_center:
    type: streamable_http
    url: http://mmb-capability-center:8097/mcp
    headers:
      Authorization: Bearer ${CAPABILITY_AUTH_TOKEN}
```

## 本地验证

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python -m unittest discover tests
DOCKER_BUILDKIT=1 docker compose build mmb-capability-center
docker compose up -d
curl http://127.0.0.1:8097/health
```

## 集成建议

第一阶段保留现有 Dify 飞书渠道接入。飞书 Bot 的主入口应用可以是 Dify Agent，也可以灰度切到 Hermes；主 Agent 只需要拿到 Capability Center 的 OpenAPI 工具和服务 token。

后续再把 Dify 前端的“渠道接入”扩展为“Bot 入口 + 能力配置”，配置主入口 Agent、可用知识范围、可用工具、部门/群聊/用户权限、个人记忆和团队记忆。
