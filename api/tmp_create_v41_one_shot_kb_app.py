from __future__ import annotations

import datetime
import json
import os
from uuid import uuid4
from typing import Any

from sqlalchemy import select

from app import app
from extensions.ext_database import db
from models import Account, App, InstalledApp
from models.dataset import AppDatasetJoin, Dataset, Pipeline
from models.workflow import Workflow

BASE_DATASET_NAME = os.getenv("BASE_DATASET_NAME", "MMB统一材料知识库-v4-表格增强")
NEW_DATASET_NAME = os.getenv("NEW_DATASET_NAME", "MMB统一材料知识库-v4.1-一次导入增强")
BASE_APP_NAME = os.getenv("BASE_APP_NAME", "MMB业务助手-v4-表格增强")
NEW_APP_NAME = os.getenv("NEW_APP_NAME", "MMB业务助手-v4.1-一次导入增强")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
PLUGIN_IDENTIFIER = os.getenv("MMB_PREPROCESSOR_PLUGIN_IDENTIFIER", "").strip()
PROVIDER_ID = "mmb/mmb_material_preprocessor/mmb_material_preprocessor"


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def utc_version() -> str:
    return str(datetime.datetime.now(datetime.UTC).replace(tzinfo=None))


def get_graph(workflow: Workflow) -> dict[str, Any]:
    return json.loads(workflow.graph) if isinstance(workflow.graph, str) else clone_json(workflow.graph)


def replace_value(value: Any, old: str, new: str) -> Any:
    if value == old:
        return new
    if isinstance(value, list):
        return [replace_value(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_value(item, old, new) for key, item in value.items()}
    return value


def tune_retrieval_model(value: Any) -> Any:
    model = clone_json(value or {})
    if isinstance(model, dict):
        model["top_k"] = int(os.getenv("V41_TOP_K", "12"))
        model["score_threshold"] = 0
        model["score_threshold_enabled"] = False
    return model


def patch_v41_graph(value: Any) -> Any:
    graph = update_preprocessor_identifier(value)

    def visit(node: Any) -> Any:
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        updated = {key: visit(item) for key, item in node.items()}
        data = updated.get("data") if isinstance(updated.get("data"), dict) else None
        if data and data.get("type") == "knowledge-retrieval":
            config = data.get("multiple_retrieval_config")
            if isinstance(config, dict):
                config["top_k"] = int(os.getenv("V41_TOP_K", "12"))
                config["score_threshold"] = 0
                config["reranking_enable"] = True
        if data and data.get("type") == "knowledge-index":
            retrieval_model = data.get("retrieval_model")
            if isinstance(retrieval_model, dict):
                retrieval_model["top_k"] = int(os.getenv("V41_TOP_K", "12"))
                retrieval_model["score_threshold"] = 0
                retrieval_model["score_threshold_enabled"] = False
        if data and data.get("type") == "code" and "检索后过滤" in str(data.get("title", "")):
            code = data.get("code") or ""
            if "narrative_context" not in code:
                code = code.replace('if "<!-- chunk_type: visual_asset -->" in lower:\n            return "visual_asset"', 'if "<!-- chunk_type: visual_asset -->" in lower:\n            return "visual_asset"\n        if "<!-- chunk_type: narrative_context -->" in lower:\n            return "narrative_context"')
                code = code.replace('{"business_fact": 0, "table_fact": 1, "text": 2, "visual_asset": 3}', '{"business_fact": 0, "table_fact": 1, "narrative_context": 2, "text": 3, "visual_asset": 4}')
                if "table_intent" not in code:
                    code = code.replace(
                        'business_terms = ("合作", "战略", "深圳文交所", "深圳文化产权交易所", "加盟", "投资", "融资", "团队", "创始", "负责人", "方案", "模式", "分润", "费用", "收益")',
                        'business_terms = ("合作", "战略", "深圳文交所", "深圳文化产权交易所", "加盟", "投资", "融资", "团队", "创始", "负责人", "方案", "模式", "分润", "费用", "收益")\n    table_terms = ("哪些人", "有哪些人", "人员", "参与", "组织架构", "职责分工", "岗位", "名单", "表格")\n    table_intent = any(term in query for term in table_terms)',
                    )
                    code = code.replace(
                        'rank = {"business_fact": 0, "table_fact": 1, "narrative_context": 2, "text": 3, "visual_asset": 4}.get(ctype, 2)',
                        'rank_map = {"business_fact": 0, "table_fact": 1, "narrative_context": 2, "text": 3, "visual_asset": 4}\n        if table_intent:\n            rank_map = {"table_fact": 0, "business_fact": 1, "narrative_context": 2, "text": 3, "visual_asset": 4}\n        rank = rank_map.get(ctype, 2)',
                    )
                data["code"] = code
        if data and data.get("type") == "llm":
            templates = data.get("prompt_template")
            if isinstance(templates, list):
                for template in templates:
                    if isinstance(template, dict) and template.get("role") == "system" and "知识库上下文" in str(template.get("text", "")) and "narrative_context" not in str(template.get("text", "")):
                        template["text"] = str(template.get("text", "")).replace("回答规则：", "回答规则：\n- 普通业务问题优先采用 chunk_type 为 business_fact、table_fact、narrative_context 的上下文；ocr_noise 只能作为视觉素材辅助信息，不能作为主依据。\n")
        return updated

    return visit(graph)


def update_preprocessor_identifier(value: Any) -> Any:
    if isinstance(value, list):
        return [update_preprocessor_identifier(item) for item in value]
    if isinstance(value, dict):
        updated = {key: update_preprocessor_identifier(item) for key, item in value.items()}
        if updated.get("provider_id") == PROVIDER_ID and PLUGIN_IDENTIFIER:
            updated["plugin_unique_identifier"] = PLUGIN_IDENTIFIER
        if str(updated.get("plugin_unique_identifier", "")).startswith("mmb/mmb_material_preprocessor:") and PLUGIN_IDENTIFIER:
            updated["plugin_unique_identifier"] = PLUGIN_IDENTIFIER
        if updated.get("tool_name") == "structure-visual-document":
            updated["title"] = "PDF/PPT/DOC One-shot Quality Enricher"
            updated["tool_label"] = "PDF/PPT/DOC One-shot Quality Enricher"
            updated["tool_description"] = "Build layout-aware typed Markdown with noise cleaning, visual/table binding, quality gate, and row-level facts before General Chunker."
        return updated
    return value


def clone_workflow(base_workflow: Workflow, app_id: str, graph: dict[str, Any], account_id: str) -> Workflow:
    return Workflow.new(
        tenant_id=base_workflow.tenant_id,
        app_id=app_id,
        type=base_workflow.type,
        version=utc_version() if base_workflow.version != "draft" else "draft",
        graph=json.dumps(graph, ensure_ascii=False),
        features=base_workflow.features,
        created_by=account_id,
        environment_variables=base_workflow.environment_variables,
        conversation_variables=base_workflow.conversation_variables,
        rag_pipeline_variables=base_workflow.rag_pipeline_variables,
        marked_name=base_workflow.marked_name or "",
        marked_comment=base_workflow.marked_comment or "",
    )


with app.app_context():
    base_dataset = db.session.scalar(select(Dataset).where(Dataset.name == BASE_DATASET_NAME).order_by(Dataset.updated_at.desc().nullslast(), Dataset.created_at.desc()))
    if not base_dataset:
        raise SystemExit(f"base dataset not found: {BASE_DATASET_NAME}")
    tenant_id = base_dataset.tenant_id

    base_app = db.session.scalar(select(App).where(App.tenant_id == tenant_id, App.name == BASE_APP_NAME).order_by(App.updated_at.desc()))
    if not base_app:
        raise SystemExit(f"base app not found: {BASE_APP_NAME}")

    account = db.session.scalar(select(Account).where(Account.email == OWNER_EMAIL)) if OWNER_EMAIL else None
    if account is None and base_app.created_by:
        account = db.session.get(Account, base_app.created_by)
    if account is None and base_dataset.created_by:
        account = db.session.get(Account, base_dataset.created_by)
    if account is None:
        account = db.session.scalar(select(Account).order_by(Account.created_at.asc()))
    if not account:
        raise SystemExit("account not found")
    account.set_tenant_id(tenant_id)

    existing_dataset = db.session.scalar(select(Dataset).where(Dataset.tenant_id == tenant_id, Dataset.name == NEW_DATASET_NAME))
    existing_app = db.session.scalar(select(App).where(App.tenant_id == tenant_id, App.name == NEW_APP_NAME))
    if existing_dataset or existing_app:
        installed = None
        if existing_app:
            installed = db.session.scalar(select(InstalledApp).where(InstalledApp.tenant_id == tenant_id, InstalledApp.app_id == existing_app.id))
        print(json.dumps({
            "exists": True,
            "dataset_id": getattr(existing_dataset, "id", None),
            "pipeline_id": getattr(existing_dataset, "pipeline_id", None),
            "app_id": getattr(existing_app, "id", None),
            "installed_app_id": getattr(installed, "id", None),
        }, ensure_ascii=False))
        raise SystemExit(0)

    base_pipeline = db.session.get(Pipeline, base_dataset.pipeline_id)
    base_pipeline_workflow = db.session.scalar(
        select(Workflow).where(Workflow.app_id == base_dataset.pipeline_id, Workflow.version != "draft").order_by(Workflow.created_at.desc())
    ) or db.session.scalar(select(Workflow).where(Workflow.app_id == base_dataset.pipeline_id, Workflow.version == "draft"))
    if not base_pipeline or not base_pipeline_workflow:
        raise SystemExit("base dataset pipeline/workflow not found")

    pipeline_graph = patch_v41_graph(get_graph(base_pipeline_workflow))
    pipeline = Pipeline(
        tenant_id=tenant_id,
        name=NEW_DATASET_NAME,
        description="统一材料知识库 V4.1：保持通用分段，新增一次导入质量门禁、短碎片治理、表格/图片上下文绑定和类型化 Markdown。",
        created_by=account.id,
        updated_by=account.id,
        is_published=True,
        is_public=True,
    )
    pipeline.id = str(uuid4())
    db.session.add(pipeline)
    db.session.flush()

    pipeline_common = dict(
        tenant_id=tenant_id,
        app_id=pipeline.id,
        type=base_pipeline_workflow.type,
        graph=json.dumps(pipeline_graph, ensure_ascii=False),
        features=base_pipeline_workflow.features,
        created_by=account.id,
        environment_variables=base_pipeline_workflow.environment_variables,
        conversation_variables=base_pipeline_workflow.conversation_variables,
        rag_pipeline_variables=base_pipeline_workflow.rag_pipeline_variables,
        marked_name="",
        marked_comment="",
    )
    pipeline_draft = Workflow.new(version="draft", **pipeline_common)
    pipeline_published = Workflow.new(version=utc_version(), **pipeline_common)
    db.session.add(pipeline_draft)
    db.session.add(pipeline_published)
    db.session.flush()
    pipeline.workflow_id = pipeline_published.id

    dataset = Dataset(
        tenant_id=tenant_id,
        name=NEW_DATASET_NAME,
        description="V4.1 一次导入增强：V4 表格增强不变，新增版面 IR、短碎片/Logo/OCR 噪声治理、类型化正文块和导入质量门禁；继续使用通用分段。",
        permission=base_dataset.permission,
        provider=base_dataset.provider,
        data_source_type=base_dataset.data_source_type,
        indexing_technique=base_dataset.indexing_technique,
        index_struct=base_dataset.index_struct,
        created_by=account.id,
        updated_by=account.id,
        embedding_model=base_dataset.embedding_model,
        embedding_model_provider=base_dataset.embedding_model_provider,
        retrieval_model=tune_retrieval_model(base_dataset.retrieval_model),
        keyword_number=base_dataset.keyword_number,
        icon_info=base_dataset.icon_info,
        runtime_mode=base_dataset.runtime_mode,
        pipeline_id=pipeline.id,
        chunk_structure="text_model",
        enable_api=True,
        is_multimodal=base_dataset.is_multimodal,
        summary_index_setting=base_dataset.summary_index_setting,
    )
    db.session.add(dataset)
    db.session.flush()

    app_graph_source = db.session.get(Workflow, base_app.workflow_id) or db.session.scalar(
        select(Workflow).where(Workflow.app_id == base_app.id, Workflow.version != "draft").order_by(Workflow.created_at.desc())
    )
    app_draft_source = db.session.scalar(select(Workflow).where(Workflow.app_id == base_app.id, Workflow.version == "draft")) or app_graph_source
    if not app_graph_source or not app_draft_source:
        raise SystemExit("base app workflow not found")

    app = App()
    app.id = str(uuid4())
    app.tenant_id = tenant_id
    app.name = NEW_APP_NAME
    app.description = "V4.1 一次导入增强：基于 V4 表格增强克隆，检索 MMB统一材料知识库-v4.1-一次导入增强，用于验证小白用户一次上传后即可获得稳定业务/表格/图片召回。"
    app.mode = base_app.mode
    app.icon_type = base_app.icon_type
    app.icon = base_app.icon
    app.icon_background = base_app.icon_background
    app.app_model_config_id = base_app.app_model_config_id
    app.status = base_app.status
    app.enable_site = base_app.enable_site
    app.enable_api = base_app.enable_api
    app.api_rpm = base_app.api_rpm
    app.api_rph = base_app.api_rph
    app.is_demo = False
    app.is_public = base_app.is_public
    app.is_universal = base_app.is_universal
    app.tracing = base_app.tracing
    app.max_active_requests = base_app.max_active_requests
    app.created_by = account.id
    app.updated_by = account.id
    app.use_icon_as_answer_icon = base_app.use_icon_as_answer_icon
    db.session.add(app)
    db.session.flush()

    published_graph = patch_v41_graph(replace_value(get_graph(app_graph_source), base_dataset.id, dataset.id))
    draft_graph = patch_v41_graph(replace_value(get_graph(app_draft_source), base_dataset.id, dataset.id))
    app_published = clone_workflow(app_graph_source, app.id, published_graph, account.id)
    app_draft = clone_workflow(app_draft_source, app.id, draft_graph, account.id)
    app_draft.version = "draft"
    db.session.add(app_draft)
    db.session.add(app_published)
    db.session.flush()
    app.workflow_id = app_published.id

    db.session.add(AppDatasetJoin(app_id=app.id, dataset_id=dataset.id))
    base_installed = db.session.scalar(select(InstalledApp).where(InstalledApp.tenant_id == tenant_id, InstalledApp.app_id == base_app.id))
    db.session.add(
        InstalledApp(
            tenant_id=tenant_id,
            app_id=app.id,
            app_owner_tenant_id=tenant_id,
            position=(base_installed.position + 1 if base_installed else 0),
            is_pinned=bool(base_installed.is_pinned) if base_installed else False,
        )
    )
    db.session.commit()

    installed = db.session.scalar(select(InstalledApp).where(InstalledApp.tenant_id == tenant_id, InstalledApp.app_id == app.id))
    print(json.dumps({
        "created": True,
        "dataset_id": dataset.id,
        "pipeline_id": pipeline.id,
        "pipeline_workflow_id": pipeline.workflow_id,
        "app_id": app.id,
        "app_workflow_id": app.workflow_id,
        "installed_app_id": installed.id if installed else None,
        "plugin_identifier": PLUGIN_IDENTIFIER or "unchanged",
    }, ensure_ascii=False))
