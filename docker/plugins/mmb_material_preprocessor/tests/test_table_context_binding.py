from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "structure_visual_document.py"


def load_module():
    dify_plugin = types.ModuleType("dify_plugin")
    dify_plugin.Tool = object
    entities = types.ModuleType("dify_plugin.entities")
    tool = types.ModuleType("dify_plugin.entities.tool")
    tool.ToolInvokeMessage = object
    sys.modules.setdefault("dify_plugin", dify_plugin)
    sys.modules.setdefault("dify_plugin.entities", entities)
    sys.modules.setdefault("dify_plugin.entities.tool", tool)
    spec = importlib.util.spec_from_file_location("structure_visual_document", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_table_context_block_binds_heading_topics_markdown_and_facts():
    module = load_module()
    tool = module.MmbVisualDocumentStructurerTool
    html = """
    <table>
      <tr><td>岗位</td><td>姓名</td><td>备注</td></tr>
      <tr><td>产品负责人</td><td>陆乘播 / Mange</td><td>开发需求对接</td></tr>
      <tr><td>全站工程师</td><td>沈豪杰</td><td>程序整体方案</td></tr>
      <tr><td>硬件 / 外部</td><td>李俊乐</td><td>对接及机器落地</td></tr>
    </table>
    """
    block = tool._format_table_context_block(
        "技术部碰头会_会议记录.docx",
        "三、团队组织架构及职责分工",
        html,
        ["主题：技术部碰头会。该主题的标题已并入正文。"],
        [],
    )
    assert "<!-- chunk_type: table_fact -->" in block
    assert "表格事实｜三、团队组织架构及职责分工" in block
    assert "技术部碰头会_会议记录.docx" in block
    assert "团队组织架构" in block
    assert "小程序开发团队" in block
    assert "| 岗位 | 姓名 | 备注 |" in block
    assert "产品负责人：陆乘播 / Mange，开发需求对接。" in block
    assert "全站工程师：沈豪杰，程序整体方案。" in block
    assert "硬件 / 外部：李俊乐，对接及机器落地。" in block



def test_structure_markdown_types_narrative_and_groups_noise():
    module = load_module()
    tool = module.MmbVisualDocumentStructurerTool
    text = """# PREFACE
→
今天
## 深圳文交所合作
MMB 与深圳文交所建立战略合作，围绕文化产权、品牌资产和交易场景开展协同。
双方计划共同推动鲜啤交易所业务落地。
"""
    body, stats = tool._structure_markdown(text, "合作方案.pdf", [])
    assert "<!-- chunk_type: business_fact -->" in body
    assert "<!-- chunk_type: ocr_noise -->" in body
    assert "主题：深圳文交所合作" in body
    assert "MMB 与深圳文交所建立战略合作" in body
    assert stats["noise_items_grouped"] >= 2


def test_table_context_uses_raw_context_not_enriched_visual_metadata():
    module = load_module()
    tool = module.MmbVisualDocumentStructurerTool
    html = """<table><tr><td>岗位</td><td>姓名</td></tr><tr><td>产品负责人</td><td>陆乘播</td></tr></table>"""
    block = tool._format_table_context_block(
        "技术部碰头会_会议记录.docx",
        "三、团队组织架构及职责分工",
        html,
        ["图像说明｜三级店型模型验证 来源：http://150.5.132.104/files/tools/demo.png", "会议明确小程序开发团队分工。"],
        [],
    )
    assert "会议明确小程序开发团队分工" in block
    assert "150.5.132.104" not in block
    assert "图片链接" not in block


def test_force_clean_does_not_wrap_markdown_table_separator():
    module = load_module()
    tool = module.MmbVisualDocumentStructurerTool
    block = """<!-- chunk_type: table_fact -->
### 表格事实｜团队组织架构
| 岗位 | 姓名 | 备注 |
| --- | --- | --- |
| 产品负责人 | 陆乘播 | 开发需求对接 |
"""
    fixed = tool._force_type_short_fragments(block, "sample.docx")
    assert "低信息 OCR/Logo 文本" not in fixed
    assert "| --- | --- | --- |" in fixed
