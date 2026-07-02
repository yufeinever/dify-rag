from __future__ import annotations

import datetime
import json
from uuid import uuid4

from sqlalchemy import select

from app import app
from extensions.ext_database import db
from models import Account
from models.dataset import Dataset, Pipeline
from models.workflow import Workflow, WorkflowType

TENANT_ID = ""
OWNER_EMAIL = ""
BASE_DATASET_NAME = "MMB统一材料知识库-V2"
NEW_NAME = "MMB统一材料知识库-v3-pdf增强"
STRUCTURER_NODE_ID = "1752498800000"
NORMALIZE_NODE_ID = "1752480460682"
AGGREGATOR_NODE_ID = "1752482022496"
PLUGIN_IDENTIFIER = "mmb/mmb_material_preprocessor:0.1.10@e3763e83cf045513ad7e9edeb8be3964ad9a01b0bba858c3ad8cdef4ea7550e3"


def clone_json(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def output_schema():
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "structure_report": {"type": "object"},
            "json": {"type": "object"},
        },
    }


def param_schemas():
    return [
        {
            "form": "llm",
            "human_description": {"en_US": "Markdown text from MMB Normalize + MinerU Parse.", "zh_Hans": "来自 MMB Normalize + MinerU Parse 的 Markdown 文本。"},
            "label": {"en_US": "Parsed Markdown", "zh_Hans": "解析 Markdown"},
            "llm_description": "Parsed Markdown text from upstream MinerU normalization node.",
            "name": "parsed_text",
            "required": True,
            "type": "string",
        },
        {
            "form": "llm",
            "human_description": {"en_US": "Optional MinerU content list JSON.", "zh_Hans": "可选的 MinerU 内容列表 JSON。"},
            "label": {"en_US": "MinerU Content List", "zh_Hans": "MinerU 内容列表"},
            "llm_description": "Optional MinerU content_list JSON for visual context binding.",
            "name": "content_list",
            "required": False,
            "type": "string",
        },
        {
            "form": "llm",
            "human_description": {"en_US": "Optional file metadata.", "zh_Hans": "可选的文件元数据。"},
            "label": {"en_US": "File Metadata", "zh_Hans": "文件元数据"},
            "llm_description": "Optional source file metadata JSON.",
            "name": "file_metadata",
            "required": False,
            "type": "string",
        },
    ]


def make_structurer_node(base_node: dict) -> dict:
    node = clone_json(base_node)
    node["id"] = STRUCTURER_NODE_ID
    node["height"] = 180
    node["position"] = {"x": 92, "y": 281}
    node["positionAbsolute"] = {"x": 92, "y": 281}
    data = node["data"]
    data.update(
        {
            "title": "PDF/PPT Visual Enricher + Structurer",
            "tool_name": "structure-visual-document",
            "tool_label": "PDF/PPT Visual Enricher + Structurer",
            "tool_description": "Bind embedded PDF/PPT images, tables, pages, and nearby headings into clean Markdown before General Chunker.",
            "plugin_id": "mmb/mmb_material_preprocessor",
            "provider_id": "mmb/mmb_material_preprocessor/mmb_material_preprocessor",
            "provider_name": "mmb_material_preprocessor",
            "provider_type": "builtin",
            "plugin_unique_identifier": PLUGIN_IDENTIFIER,
            "tool_configurations": {},
            "tool_parameters": {
                "parsed_text": {"type": "variable", "value": [NORMALIZE_NODE_ID, "text"]},
                "content_list": {"type": "mixed", "value": "{{#1752480460682.content_list_text#}}"},
                "file_metadata": {"type": "mixed", "value": "{{#1752480460682.json.file_metadata#}}"},
            },
            "output_schema": output_schema(),
            "paramSchemas": param_schemas(),
            "type": "tool",
            "tool_node_version": "2",
            "selected": False,
        }
    )
    return node


def replace_variable_refs(value):
    if value == [NORMALIZE_NODE_ID, "text"]:
        return [STRUCTURER_NODE_ID, "text"]
    if isinstance(value, list):
        return [replace_variable_refs(v) for v in value]
    if isinstance(value, dict):
        return {k: replace_variable_refs(v) for k, v in value.items()}
    return value


def update_graph(base_graph: dict) -> dict:
    graph = clone_json(base_graph)
    nodes = graph["nodes"]
    edges = graph["edges"]
    normalize = next(n for n in nodes if n.get("id") == NORMALIZE_NODE_ID or n.get("data", {}).get("tool_name") == "normalize-file")
    if normalize.get("id") != NORMALIZE_NODE_ID:
        raise RuntimeError("normalize node id mismatch; script expects V2 graph ids")
    if not any(n.get("id") == STRUCTURER_NODE_ID for n in nodes):
        nodes.append(make_structurer_node(normalize))

    for node in nodes:
        data = node.get("data", {})
        if data.get("provider_id") == "mmb/mmb_material_preprocessor/mmb_material_preprocessor":
            data["plugin_unique_identifier"] = PLUGIN_IDENTIFIER
        if data.get("tool_name") == "normalize-file":
            props = data.setdefault("output_schema", {}).setdefault("properties", {})
            props.setdefault("content_list", {"type": "array", "items": {"type": "object"}})
            props.setdefault("content_list_text", {"type": "string"})
        if node.get("id") == AGGREGATOR_NODE_ID:
            data["variables"] = replace_variable_refs(data.get("variables", []))
            data["advanced_settings"] = replace_variable_refs(data.get("advanced_settings", {}))
        if data.get("type") == "knowledge-index":
            data["chunk_structure"] = "text_model"
            data["indexing_technique"] = "high_quality"

    edges[:] = [
        e for e in edges
        if not (e.get("source") == NORMALIZE_NODE_ID and e.get("target") == AGGREGATOR_NODE_ID)
        and e.get("id") not in {
            f"{NORMALIZE_NODE_ID}-source-{STRUCTURER_NODE_ID}-target",
            f"{STRUCTURER_NODE_ID}-source-{AGGREGATOR_NODE_ID}-target",
        }
    ]
    edges.append(
        {
            "data": {"isInIteration": False, "isInLoop": False, "sourceType": "tool", "targetType": "tool"},
            "id": f"{NORMALIZE_NODE_ID}-source-{STRUCTURER_NODE_ID}-target",
            "source": NORMALIZE_NODE_ID,
            "sourceHandle": "source",
            "target": STRUCTURER_NODE_ID,
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
        }
    )
    edges.append(
        {
            "data": {"isInIteration": False, "isInLoop": False, "sourceType": "tool", "targetType": "variable-aggregator"},
            "id": f"{STRUCTURER_NODE_ID}-source-{AGGREGATOR_NODE_ID}-target",
            "source": STRUCTURER_NODE_ID,
            "sourceHandle": "source",
            "target": AGGREGATOR_NODE_ID,
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
        }
    )
    graph["viewport"] = {"x": 620, "y": 160, "zoom": 0.72}
    return graph


with app.app_context():
    base_dataset = db.session.scalar(select(Dataset).where(Dataset.name == BASE_DATASET_NAME).order_by(Dataset.updated_at.desc().nullslast(), Dataset.created_at.desc()))
    if not base_dataset:
        raise SystemExit(f"base dataset not found: {BASE_DATASET_NAME}")
    tenant_id = TENANT_ID or base_dataset.tenant_id
    account = None
    if OWNER_EMAIL:
        account = db.session.scalar(select(Account).where(Account.email == OWNER_EMAIL))
    if account is None and base_dataset.created_by:
        account = db.session.get(Account, base_dataset.created_by)
    if account is None:
        account = db.session.scalar(select(Account).order_by(Account.created_at.asc()))
    if not account:
        raise SystemExit("account not found")
    account.set_tenant_id(tenant_id)

    existing = db.session.scalar(select(Dataset).where(Dataset.tenant_id == tenant_id, Dataset.name == NEW_NAME))
    if existing:
        print(json.dumps({"exists": True, "dataset_id": existing.id, "pipeline_id": existing.pipeline_id}, ensure_ascii=False))
        raise SystemExit(0)
    base_pipeline = db.session.get(Pipeline, base_dataset.pipeline_id)
    base_workflow = db.session.scalar(
        select(Workflow).where(Workflow.app_id == base_dataset.pipeline_id, Workflow.version != "draft").order_by(Workflow.created_at.desc())
    ) or db.session.scalar(select(Workflow).where(Workflow.app_id == base_dataset.pipeline_id, Workflow.version == "draft"))
    if not base_pipeline or not base_workflow:
        raise SystemExit("base pipeline/workflow not found")

    base_graph = json.loads(base_workflow.graph) if isinstance(base_workflow.graph, str) else base_workflow.graph
    graph = update_graph(base_graph)

    pipeline = Pipeline(
        tenant_id=base_dataset.tenant_id,
        name=NEW_NAME,
        description="统一材料知识库 V3：保持通用分段，增强 PDF/PPT 内嵌图片、表格和页面上下文结构化。",
        created_by=account.id,
        updated_by=account.id,
        is_published=True,
        is_public=True,
    )
    pipeline.id = str(uuid4())
    db.session.add(pipeline)
    db.session.flush()

    version = str(datetime.datetime.now(datetime.UTC).replace(tzinfo=None))
    common = dict(
        tenant_id=pipeline.tenant_id,
        app_id=pipeline.id,
        type=WorkflowType.RAG_PIPELINE,
        graph=json.dumps(graph, ensure_ascii=False),
        features=base_workflow.features,
        created_by=account.id,
        environment_variables=base_workflow.environment_variables,
        conversation_variables=base_workflow.conversation_variables,
        rag_pipeline_variables=base_workflow.rag_pipeline_variables,
        marked_name="",
        marked_comment="",
    )
    draft = Workflow.new(version="draft", **common)
    published = Workflow.new(version=version, **common)
    db.session.add(draft)
    db.session.add(published)
    db.session.flush()
    pipeline.workflow_id = published.id

    dataset = Dataset(
        tenant_id=base_dataset.tenant_id,
        name=NEW_NAME,
        description="V3 PDF增强：通用分段模式不变，在分段前对 PDF/PPT 内嵌图片、图表、人物页、产品页做来源和上下文绑定。",
        permission=base_dataset.permission,
        provider=base_dataset.provider,
        data_source_type=base_dataset.data_source_type,
        indexing_technique=base_dataset.indexing_technique,
        index_struct=base_dataset.index_struct,
        created_by=account.id,
        updated_by=account.id,
        embedding_model=base_dataset.embedding_model,
        embedding_model_provider=base_dataset.embedding_model_provider,
        retrieval_model=base_dataset.retrieval_model,
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
    db.session.commit()
    print(json.dumps({"created": True, "dataset_id": dataset.id, "pipeline_id": pipeline.id, "draft_workflow_id": draft.id, "published_workflow_id": published.id}, ensure_ascii=False))
