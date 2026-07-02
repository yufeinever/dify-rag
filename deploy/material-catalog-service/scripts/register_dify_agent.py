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


APP_NAME = "资料全知agent"
LEGACY_APP_NAME = "资料全知agent v1 workflow"
MCP_NAME = "资料全知材料探索"
MCP_IDENTIFIER = "material_catalog_mcp"
MCP_URL = "http://material-catalog-service:8091/mcp"
TOOL_NAMES = [
    "server_info",
    "list_material_roots",
    "list_datasets",
    "list_documents",
    "search_segments",
    "read_document_chunks",
    "search_files",
    "read_file_text",
    "profile_materials",
    "list_material_changes",
]

AGENT_PROMPT = """你是“资料全知agent”，一个只读的材料探索 Agent。

工作范围限定在当前 150 Dify 材料范围：Dify storage 与 Dify 元数据库中已经登记、索引或上传的材料。不要声称可以访问范围外文件。

你不是固定 workflow，也不是只聊天的机器人。你应该根据问题自主选择 MCP 工具：
- 事实问题必须先调用 search_segments 查证据；必要时用 read_document_chunks 扩上下文。
- 问“有哪些材料/材料结构/材料画像”时，优先调用 profile_materials、list_material_roots、list_datasets、list_documents。
- 问“最近变化”时，调用 list_material_changes。
- 问文件位置或文件名时，调用 search_files；只有文本类文件且确有必要时才调用 read_file_text。
- 用户要求展示图片、Logo、海报、照片或“给我看图”时，先调用 search_files；如果工具结果包含 thumbnail_markdown_image，必须原样输出 thumbnail_markdown_image，让前端直接渲染压缩预览图，并同时给出来源文件名和 original_link_markdown。只有没有 thumbnail_markdown_image 时才退回 markdown_image。不要只给 relative_path、storage 路径或预览路径。
- 用户要求展示 Markdown 文件内容时，先调用 read_file_text；如果返回 render_as=markdown，直接按 Markdown 保留标题、列表、表格和图片语法输出。
- PDF/DOCX/PPTX 等文档证据不要在正文混入预览图；优先输出 document_link_markdown，让用户点进文档管理模块查看详情。
- 行业资料、Agent/RAG 方法论只能作为工作方法，不得当作 MMB 业务事实证据；业务事实必须来自 150 Dify 材料证据。
- 用户要求删除、移动、覆盖、重新入库、改写材料时，必须拒绝直接执行，只能给出需人工确认的只读分析或操作计划。

回答要求：
1. 结论必须来自工具证据，不能凭记忆猜。
2. 回答事实时必须带来源文档链接、chunk 位置和原文片段；优先使用 document_link_markdown 和 segment_position，至少列出可支撑结论的证据。
3. 如果工具没有找到证据，明确说“当前 150 Dify 材料范围内未找到”。
4. 不暴露数据库密码、私钥、敏感绝对路径、storage 绝对路径或内部密钥内容。
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
                icon="📚",
                icon_type="emoji",
                icon_background="#E8F2FF",
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
                description="只读材料探索 MCP Agent，会自主调用工具查证据并引用来源。",
                mode="agent-chat",
                icon_type="emoji",
                icon="📚",
                icon_background="#E8F2FF",
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
            "max_iteration": 8,
        },
        ensure_ascii=False,
    )
    app_model_config.suggested_questions = json.dumps(
        ["MMB 的创始人是谁？", "目前有哪些材料？", "最近材料有什么变化？", "融资方案在哪里？"],
        ensure_ascii=False,
    )
    app_model_config.opening_statement = "我是资料全知agent。你提问题后，我会先查 150 Dify 材料范围内的证据，再给结论和来源。"
    app_model_config.updated_by = user_id
    agent_app.description = "只读材料探索 MCP Agent，会自主调用工具查证据并引用来源。"
    agent_app.icon_type = "emoji"
    agent_app.icon = "📚"
    agent_app.icon_background = "#E8F2FF"
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
