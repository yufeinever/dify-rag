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
