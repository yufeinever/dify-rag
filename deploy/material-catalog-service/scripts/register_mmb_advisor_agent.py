from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app import app
from core.db.session_factory import session_factory
from core.entities.agent_entities import PlanningStrategy
from core.entities.mcp_provider import MCPConfiguration
from core.tools.entities.tool_entities import ToolProviderType
from extensions.ext_database import db
from models import Account, ExploreAppPermission, InstalledApp, TenantAccountJoin, TenantAccountRole
from models.model import App, AppMode
from models.tools import MCPToolProvider
from services.app_service import AppService, CreateAppParams
from services.tools.mcp_tools_manage_service import MCPToolManageService


APP_NAME = "MMB智囊"
LEGACY_APP_NAME = "MMB智囊 legacy workflow"
MCP_NAME = "MMB智囊内外研究工具"
MCP_IDENTIFIER = "mmb_advisor_mcp"
MCP_URL = "http://material-catalog-service:8091/mcp"
TOOL_NAMES = [
    "server_info",
    "list_material_roots",
    "list_datasets",
    "list_documents",
    "search_segments",
    "read_document_chunks",
    "search_files",
    "search_visual_assets",
    "find_person_visual_candidates",
    "read_file_text",
    "profile_materials",
    "list_material_changes",
    "web_search",
    "read_web_page",
    "summarize_web_sources",
    "github_search_repositories",
    "github_search_code",
    "github_read_file",
    "github_list_issues",
    "github_list_pull_requests",
    "github_list_actions_runs",
    "github_prepare_issue",
]

AGENT_PROMPT = """你是“MMB智囊”，一个面向 MMB 内部的战略顾问型 Agent。你的能力不是只复述内部材料，而是把 MMB 内部证据、外部资料和你的专业推理分层整合，给出可执行建议。

核心定位：
- 超级内脑/资料全知agent负责严格材料内查证；你负责“内证据 + 外部视野 + 受控执行建议”。
- 当问题涉及 MMB 事实、公司定位、创始人、融资方案、产品规划、材料图片时，先调用内部材料工具建立事实底座。
- 当问题涉及行业、竞品、开源项目、GitHub、实时信息、技术选型、市场案例、政策/价格/天气等外部变化时，必须主动调用外部工具，不要只用内部材料保守回答。

工具策略：
- 内部事实：search_segments、read_document_chunks、search_files、search_visual_assets、find_person_visual_candidates、profile_materials、list_material_changes。
- 外部网页：web_search 找来源，read_web_page 读取原文，summarize_web_sources 做多来源摘录。外部资料只能作为外部参考，不能当作 MMB 内部事实。
- GitHub：github_search_repositories、github_search_code、github_read_file、github_list_issues、github_list_pull_requests、github_list_actions_runs。
- 执行草稿：github_prepare_issue 只能生成 issue 草稿和确认计划；公开发布、删除、生产变更、付费动作、对外发帖、真实 GitHub 写入都必须先给确认计划，不能假装已经执行。

回答结构默认使用：
1. 结论
2. MMB内部依据
3. 外部参考
4. 建议动作
5. 风险与待确认

证据规则：
- MMB 内部事实必须带 document_link_markdown、chunk 位置和原文片段。
- 外部资料必须带网页/GitHub 链接和读取到的关键摘录。
- 模型推理必须明确标注为“推理/建议”，不能伪装成证据。
- 找不到内部证据时说“当前 150 Dify 材料范围内未找到”；找不到外部工具或未配置搜索 key 时说清楚缺哪个工具/配置，并给可替代的下一步。
- 禁止暴露数据库密码、私钥、敏感绝对路径、storage 绝对路径或内部密钥内容。
"""

def pick_tenant_and_user() -> tuple[str, str]:
    existing_app = db.session.scalar(select(App).where(App.name == APP_NAME).order_by(App.created_at.desc()))
    if existing_app:
        return existing_app.tenant_id, existing_app.created_by

    join = db.session.scalar(
        select(TenantAccountJoin)
        .where(TenantAccountJoin.role.in_([TenantAccountRole.OWNER, TenantAccountRole.ADMIN]))
        .order_by(TenantAccountJoin.created_at.asc())
    )
    if not join:
        join = db.session.scalar(select(TenantAccountJoin).order_by(TenantAccountJoin.created_at.asc()))
    if not join:
        raise RuntimeError("No tenant/account join found")
    return join.tenant_id, join.account_id


def ensure_mcp_provider(tenant_id: str, user_id: str) -> MCPToolProvider:
    config = MCPConfiguration(timeout=30, sse_read_timeout=300)
    reconnect = MCPToolManageService.reconnect_with_url(
        server_url=MCP_URL,
        headers={},
        timeout=config.timeout,
        sse_read_timeout=config.sse_read_timeout,
    )

    with session_factory.create_session() as session, session.begin():
        service = MCPToolManageService(session=session)
        provider = session.scalar(
            select(MCPToolProvider).where(
                MCPToolProvider.tenant_id == tenant_id,
                MCPToolProvider.server_identifier == MCP_IDENTIFIER,
            )
        )
        if not provider:
            service.create_provider(
                tenant_id=tenant_id,
                user_id=user_id,
                server_url=MCP_URL,
                name=MCP_NAME,
                icon="🧠",
                icon_type="emoji",
                icon_background="#EEF2FF",
                server_identifier=MCP_IDENTIFIER,
                headers={},
                configuration=config,
                authentication=None,
            )
            provider = service.get_provider(server_identifier=MCP_IDENTIFIER, tenant_id=tenant_id)
        else:
            service.update_provider(
                tenant_id=tenant_id,
                provider_id=provider.id,
                name=MCP_NAME,
                server_url=MCP_URL,
                icon="📚",
                icon_type="emoji",
                icon_background="#E8F2FF",
                server_identifier=MCP_IDENTIFIER,
                headers={},
                configuration=config,
                authentication=None,
            )
        provider.authed = reconnect.authed
        provider.tools = reconnect.tools
        provider.encrypted_credentials = reconnect.encrypted_credentials
        session.flush()
        provider_id = provider.id

    return db.session.get(MCPToolProvider, provider_id)


def unique_legacy_name(tenant_id: str) -> str:
    if not db.session.scalar(select(App).where(App.tenant_id == tenant_id, App.name == LEGACY_APP_NAME)):
        return LEGACY_APP_NAME
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{LEGACY_APP_NAME} {suffix}"


def ensure_agent_app(tenant_id: str, user_id: str, provider: MCPToolProvider) -> App:
    account = db.session.get(Account, user_id)
    if not account:
        raise RuntimeError(f"Account not found: {user_id}")
    account.set_tenant_id(tenant_id)

    apps = list(db.session.scalars(select(App).where(App.tenant_id == tenant_id, App.name == APP_NAME)))
    agent_app = next((item for item in apps if item.mode == AppMode.AGENT_CHAT), None)
    if not agent_app:
        legacy_name = unique_legacy_name(tenant_id)
        for item in apps:
            if item.mode != AppMode.AGENT_CHAT:
                item.name = legacy_name
                item.updated_by = user_id
        db.session.commit()
        agent_app = AppService().create_app(
            tenant_id,
            CreateAppParams(
                name=APP_NAME,
                description="MMB 内证据 + 外部视野 + 受控执行的战略顾问 Agent。",
                mode="agent-chat",
                icon_type="emoji",
                icon="🧠",
                icon_background="#EEF2FF",
            ),
            account,
        )

    app_model_config = agent_app.app_model_config
    if not app_model_config:
        raise RuntimeError(f"App model config missing: {agent_app.id}")

    tools = [
        {
            "provider_type": ToolProviderType.MCP.value,
            "provider_id": MCP_IDENTIFIER,
            "tool_name": tool_name,
            "tool_parameters": {},
            "enabled": True,
        }
        for tool_name in TOOL_NAMES
    ]
    app_model_config.pre_prompt = AGENT_PROMPT
    app_model_config.agent_mode = json.dumps(
        {
            "enabled": True,
            "strategy": PlanningStrategy.FUNCTION_CALL.value,
            "tools": tools,
            "prompt": None,
            "max_iteration": 12,
        },
        ensure_ascii=False,
    )
    app_model_config.suggested_questions = json.dumps(
        ["MMB 如果做自助鲜啤设备 SaaS，技术方案怎么选？", "类似 MMB 的鲜啤/自助售卖模式国外有什么案例？", "有没有适合做 Agent 工具调用的开源项目？", "帮我起草一个 GitHub issue"],
        ensure_ascii=False,
    )
    app_model_config.opening_statement = "我是 MMB智囊。我会先查 MMB 内部材料形成事实底座，再结合外部网页、GitHub 和行业资料给你建议，并区分证据与推理。"
    app_model_config.updated_by = user_id
    agent_app.description = "MMB 内证据 + 外部视野 + 受控执行的战略顾问 Agent。"
    agent_app.icon_type = "emoji"
    agent_app.icon = "🧠"
    agent_app.icon_background = "#EEF2FF"
    agent_app.updated_by = user_id
    db.session.commit()
    return agent_app


def ensure_explore_install(tenant_id: str, app_id: str) -> None:
    installed = db.session.scalar(
        select(InstalledApp).where(InstalledApp.tenant_id == tenant_id, InstalledApp.app_id == app_id)
    )
    if not installed:
        db.session.add(
            InstalledApp(
                tenant_id=tenant_id,
                app_id=app_id,
                app_owner_tenant_id=tenant_id,
                position=0,
                is_pinned=True,
            )
        )

    account_ids = list(
        db.session.scalars(select(TenantAccountJoin.account_id).where(TenantAccountJoin.tenant_id == tenant_id))
    )
    existing = set(
        db.session.scalars(
            select(ExploreAppPermission.account_id).where(
                ExploreAppPermission.tenant_id == tenant_id,
                ExploreAppPermission.app_id == app_id,
            )
        )
    )
    for account_id in account_ids:
        if account_id not in existing:
            db.session.add(
                ExploreAppPermission(
                    tenant_id=tenant_id,
                    app_id=app_id,
                    account_id=account_id,
                    has_permission=True,
                )
            )
    db.session.commit()


with app.app_context():
    tenant_id, user_id = pick_tenant_and_user()
    provider = ensure_mcp_provider(tenant_id, user_id)
    agent_app = ensure_agent_app(tenant_id, user_id, provider)
    ensure_explore_install(tenant_id, agent_app.id)
    print(
        json.dumps(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "provider_id": provider.id,
                "provider_identifier": provider.server_identifier,
                "provider_authed": provider.authed,
                "tool_count": len(json.loads(provider.tools or "[]")),
                "app_id": agent_app.id,
                "app_name": agent_app.name,
                "app_mode": agent_app.mode.value,
            },
            ensure_ascii=False,
        )
    )
