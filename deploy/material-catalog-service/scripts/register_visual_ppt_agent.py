from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app import app
from core.entities.agent_entities import PlanningStrategy
from extensions.ext_database import db
from models import Account, ExploreAppPermission, InstalledApp, TenantAccountJoin, TenantAccountRole
from models.model import App, AppMode
from services.app_service import AppService, CreateAppParams


APP_NAME = "MMB视觉PPT助手"
LEGACY_APP_NAME = "MMB视觉PPT助手 legacy"

VISUAL_PPT_TOOL = {
    "provider_type": "builtin",
    "provider_id": "mmb/visual_ppt_tools/visual_ppt_tools",
    "provider_name": "visual_ppt_tools",
    "plugin_id": "mmb/visual_ppt_tools",
    "tool_name": "create_visual_ppt_deck",
    "tool_label": "Create Visual PPT Deck",
    "tool_description": "Generate image-first PowerPoint decks. Each slide is a full 16:9 generated image.",
    "tool_parameters": {},
    "tool_configurations": {},
    "enabled": True,
    "isDeleted": False,
    "notAuthor": False,
}

AGENT_PROMPT = """你是“MMB视觉PPT助手”，专门生成图片型 PPT。

核心规则：
- 你的目标不是输出文字方案，而是生成可下载的 .pptx 附件。
- 用户要求做 PPT、路演稿、汇报稿、提案、营销方案、融资材料、视觉版演示文稿时，必须调用 create_visual_ppt_deck。
- 每页 PPT 都应是完整 16:9 视觉页面图，不使用旧式标题框 + bullet 列表排版。
- 先把用户需求整理成清晰页面大纲，再调用工具。不要只用文字回复。

页面规划：
- 默认 6 页：封面、背景/机会、核心方案、执行路径、预期效果、总结/行动。
- 如果用户给了明确页数，按用户页数，但最多 12 页。
- 每页只保留一个短标题和 2-4 个极短关键词，避免小字密集。
- 中文可以出现在画面里，但必须短、大、清晰；不要生成长段中文。

工具调用：
- 工具名：create_visual_ppt_deck。
- title 使用用户主题。
- outline 使用整理后的 Markdown 大纲。
- slides_json 可选；如果你能整理成结构化页面数组，优先传 slides_json。
- filename 使用中文文件名并以 .pptx 结尾。
- style_preset 默认 mmb_modern_pitch，除非用户要求其他风格。
- slide_count 默认 6，最多 12。

成功后：
- 简短说明文件名、页数、风格。
- 提醒用户在下方附件卡片下载。
- 只有工具调用成功后，才能说“已生成”。
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


def unique_legacy_name(tenant_id: str) -> str:
    if not db.session.scalar(select(App).where(App.tenant_id == tenant_id, App.name == LEGACY_APP_NAME)):
        return LEGACY_APP_NAME
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{LEGACY_APP_NAME} {suffix}"


def ensure_agent_app(tenant_id: str, user_id: str) -> App:
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
                description="把大纲转成整页图片型 PPT 的专用 Agent。",
                mode="agent-chat",
                icon_type="emoji",
                icon="🎞️",
                icon_background="#EEF2FF",
            ),
            account,
        )

    app_model_config = agent_app.app_model_config
    if not app_model_config:
        raise RuntimeError(f"App model config missing: {agent_app.id}")

    app_model_config.pre_prompt = AGENT_PROMPT
    app_model_config.agent_mode = json.dumps(
        {
            "enabled": True,
            "strategy": PlanningStrategy.FUNCTION_CALL.value,
            "tools": [VISUAL_PPT_TOOL],
            "prompt": None,
            "max_iteration": 6,
        },
        ensure_ascii=False,
    )
    app_model_config.suggested_questions = json.dumps(
        [
            "做一个 MMB 端午节营销方案视觉 PPT",
            "把自助鲜啤设备 SaaS 方案做成 6 页图片型 PPT",
            "做一个融资路演视觉版 PPT",
            "根据这个大纲生成视觉演示文稿",
        ],
        ensure_ascii=False,
    )
    app_model_config.opening_statement = "我是 MMB视觉PPT助手。给我主题或大纲，我会把它做成整页图片型 PPT 附件。"
    app_model_config.updated_by = user_id
    agent_app.description = "把大纲转成整页图片型 PPT 的专用 Agent。"
    agent_app.icon_type = "emoji"
    agent_app.icon = "🎞️"
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
    agent_app = ensure_agent_app(tenant_id, user_id)
    ensure_explore_install(tenant_id, agent_app.id)
    print(
        json.dumps(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "app_id": agent_app.id,
                "app_name": agent_app.name,
                "mode": agent_app.mode.value if hasattr(agent_app.mode, "value") else str(agent_app.mode),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
