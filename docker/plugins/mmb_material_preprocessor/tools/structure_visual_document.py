from __future__ import annotations

import json
import re
from collections.abc import Generator
from typing import Any

from bs4 import BeautifulSoup
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ROLE_HEADING_RE = re.compile(r"^#{1,6}\s*(创始人|創始人|技术负责人|技術負責人|资本负责人|資本負責人|CEO|CTO|CFO|负责人|負責人)[:：]\s*(.+?)\s*$", re.I)
TYPED_CHUNK_RE = re.compile(r"<!--\s*chunk_type:\s*([a-z_]+)\s*-->", re.I)
RAW_URL_RE = re.compile(r"^(?:https?://|/files/)[^\s]+$", re.I)
PUNCT_ONLY_RE = re.compile(r"^[\s\-–—_.,，。:：;；|/\\!！?？()（）\[\]【】<>《》·…•*+=$￥¥→←↑↓]+$")

BRAND_ALIASES = "MMB、瞢瞢熊、懵懵熊、麦乐迪智慧鲜啤交易所"
LOW_INFO_TERMS = {
    "mmb",
    "瞢瞢熊",
    "懵懵熊",
    "麦乐迪",
    "智慧鲜啤",
    "麦乐迪智慧鲜啤交易所",
}
UI_NOISE_TERMS = {
    "今天",
    "发消息",
    "已关注公众号",
    "作者精选",
    "朋友读过",
    "视频号服务",
    "商家",
    "提货",
    "……",
}
SOURCE_META_PREFIXES = ("来源：", "图片链接：", "结构化信息：图片已绑定", "用途：", "[来源:")
SIGNIFICANT_SHORT_TERMS = {"合作", "融资", "产品", "加盟", "团队", "职责", "岗位", "姓名", "备注", "金额", "收益", "费用", "分润", "估值", "退出", "轮次", "模式", "设备", "参数", "人员", "A轮", "B轮", "IP", "UI", "CEO", "CTO", "CFO"}
MAX_NARRATIVE_CHARS = 900
MAX_NOISE_ITEMS = 24
TOPIC_DEFINITIONS = (
    (
        "cooperation",
        "business_fact",
        "深圳文交所战略合作事实摘要",
        ("深圳文交所", "深圳文化产权交易所", "文化产权交易所", "深圳市文化金融服务中心", "深文所", "战略合作", "合作"),
        "战略合作、合作关系、合作内容、合作海报、深圳文交所、深圳文化产权交易所",
    ),
    (
        "franchise",
        "business_fact",
        "加盟/投资合作事实摘要",
        ("加盟", "合伙", "代理", "投资", "合作方式", "加入方式", "分润", "门店", "城市合伙", "区域合伙", "费用", "收益"),
        "加盟方式、合作模式、投资合作、分润、门槛、适合对象",
    ),
    (
        "financing",
        "business_fact",
        "融资方案事实摘要",
        ("融资", "天使轮", "A轮", "B轮", "估值", "退出", "并购", "上市", "投资人", "资本"),
        "融资方案、轮次、金额、估值、退出路径",
    ),
    (
        "product",
        "business_fact",
        "产品/业务模式事实摘要",
        ("产品", "参数", "鲜啤", "小程序", "售货机", "设备", "业务模式", "应用场景", "门店", "IP"),
        "产品参数、业务模式、应用场景、智慧鲜啤",
    ),
)


class MmbVisualDocumentStructurerTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        parsed_text = self._as_text(tool_parameters.get("parsed_text")).strip()
        if not parsed_text:
            raise ValueError("parsed_text is required")

        content_list = self._parse_jsonish(tool_parameters.get("content_list"))
        file_metadata = self._parse_jsonish(tool_parameters.get("file_metadata"))
        if not isinstance(content_list, list):
            content_list = []
        if not isinstance(file_metadata, dict):
            file_metadata = self._metadata_from_text(parsed_text)

        filename = str(
            file_metadata.get("source_file_name")
            or file_metadata.get("normalized_file_name")
            or file_metadata.get("filename")
            or "source document"
        )
        extension = str(file_metadata.get("file_extension") or "").lower()

        layout_blocks = self._build_layout_ir(content_list)
        cleaned_text = self._clean_tables(self._strip_normalize_preamble(parsed_text))
        structured_body, stats = self._structure_markdown(cleaned_text, filename, layout_blocks)
        key_fact_sections = self._build_topic_fact_sections(cleaned_text, filename)
        visual_sections = self._build_visual_sections(layout_blocks, filename)

        output_parts: list[str] = []
        if key_fact_sections:
            output_parts.extend(key_fact_sections + [""])
        if visual_sections:
            output_parts.extend(visual_sections + [""])
        output_parts.extend([structured_body.strip(), ""])
        output = "\n".join(output_parts).strip() + "\n"
        quality_gate = self._quality_gate(output, stats)
        if not quality_gate["passed"]:
            output = self._force_type_short_fragments(output, filename)
            stats["quality_retry"] += 1
            quality_gate = self._quality_gate(output, stats)

        report = {
            "parser": "mmb-visual-document-structurer",
            "version": "0.1.16",
            "source_file_name": filename,
            "file_extension": extension,
            "content_items": len(content_list),
            "layout_blocks": len(layout_blocks),
            "visual_sections": len(visual_sections),
            "short_heading_merges": stats["short_heading_merges"],
            "image_placeholders": stats["image_placeholders"],
            "tables_normalized": stats["tables_normalized"],
            "noise_blocks_marked": stats["noise_blocks_marked"],
            "noise_items_grouped": stats["noise_items_grouped"],
            "narrative_blocks": stats["narrative_blocks"],
            "topic_fact_sections": len(key_fact_sections),
            "quality_gate": quality_gate,
            "strategy": "one_shot_layout_ir_noise_clean_table_visual_context_general_chunker_input",
        }

        yield self.create_variable_message("structure_report", report)
        yield self.create_text_message(output)
        yield self.create_json_message({"text": output, "structure_report": report})

    @staticmethod
    def _strip_normalize_preamble(text: str) -> str:
        marker = "# 解析正文"
        if marker in text:
            return text.split(marker, 1)[1].strip()
        return text

    @classmethod
    def _build_topic_fact_sections(cls, text: str, filename: str) -> list[str]:
        team_members: list[str] = []
        lines = [line.strip() for line in text.splitlines()]
        i = 0
        while i < len(lines):
            match = ROLE_HEADING_RE.match(lines[i])
            if not match:
                i += 1
                continue
            role = match.group(1).replace("創始人", "创始人").replace("技術負責人", "技术负责人").replace("資本負責人", "资本负责人")
            name = match.group(2).strip()
            body: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt:
                    j += 1
                    if body:
                        break
                    continue
                if HEADING_RE.match(nxt) or IMAGE_RE.fullmatch(nxt) or "<table" in nxt.lower():
                    break
                body.append(nxt)
                j += 1
                if cls._wordish_len("".join(body)) >= 120:
                    break
            desc = " ".join(part for part in body if part).strip()
            if name:
                team_members.append(f"{role}：{name}" + (f"，{desc}" if desc else ""))
            i = max(j, i + 1)

        sections: list[str] = []
        if team_members:
            sections.append(
                cls._format_summary_block(
                    "business_fact",
                    "核心团队事实摘要",
                    [
                        f"相关主体：{BRAND_ALIASES}",
                        "相关主题：核心团队、创始人、负责人、团队成员",
                        "关键事实：" + "；".join(team_members),
                        f"来源：{filename}，核心团队页面/邻近章节。",
                    ],
                )
            )

        normalized_lines = cls._candidate_fact_lines(text)
        used_fingerprints: set[str] = set()
        for _, chunk_type, title, keywords, related in TOPIC_DEFINITIONS:
            matched = cls._collect_topic_lines(normalized_lines, keywords)
            if not matched:
                continue
            fingerprint = "|".join(matched[:3])
            if fingerprint in used_fingerprints:
                continue
            used_fingerprints.add(fingerprint)
            sections.append(
                cls._format_summary_block(
                    chunk_type,
                    title,
                    [
                        f"相关主体：{BRAND_ALIASES}",
                        f"相关主题：{related}",
                        "关键事实：" + "；".join(matched[:8]),
                        f"来源：{filename}，按正文/视觉上下文自动提取。",
                    ],
                )
            )
        return sections[:8]

    @classmethod
    def _candidate_fact_lines(cls, text: str) -> list[str]:
        candidates: list[str] = []
        for raw in text.splitlines():
            line = BeautifulSoup(raw.strip(), "html.parser").get_text(" ", strip=True)
            line = re.sub(r"^[#>*\-\s]+", "", line).strip()
            line = re.sub(r"\s+", " ", line)
            if not line or cls._is_low_info_text(line):
                continue
            if IMAGE_RE.fullmatch(line) or line.lower().startswith(("http://", "https://", "/files/")):
                continue
            if cls._wordish_len(line) < 8:
                continue
            candidates.append(line[:240])
        return candidates

    @staticmethod
    def _collect_topic_lines(lines: list[str], keywords: tuple[str, ...]) -> list[str]:
        return [line for line in lines if any(keyword.lower() in line.lower() for keyword in keywords)][:12]

    @classmethod
    def _structure_markdown(cls, text: str, filename: str, layout_blocks: list[dict[str, Any]] | None = None) -> tuple[str, dict[str, int]]:
        lines = [line.rstrip() for line in text.splitlines()]
        output: list[str] = []
        stats = {
            "short_heading_merges": 0,
            "image_placeholders": 0,
            "tables_normalized": 0,
            "noise_blocks_marked": 0,
            "noise_items_grouped": 0,
            "narrative_blocks": 0,
            "quality_retry": 0,
        }
        pending_images: list[str] = []
        narrative_buffer: list[str] = []
        noise_buffer: list[str] = []
        recent_context: list[str] = []
        last_heading = ""

        def remember_context(value: str) -> None:
            cleaned = cls._clean_inline_text(value)
            if not cleaned or cls._is_low_info_text(cleaned) or cls._is_context_noise_text(cleaned):
                return
            recent_context.append(cleaned[:180])
            del recent_context[:-8]

        def flush_noise() -> None:
            nonlocal noise_buffer
            if not noise_buffer:
                return
            output.append(cls._format_noise_block("\n".join(f"- {item}" for item in noise_buffer), filename))
            stats["noise_blocks_marked"] += 1
            stats["noise_items_grouped"] += len(noise_buffer)
            noise_buffer = []

        def flush_narrative() -> None:
            nonlocal narrative_buffer
            normalized = cls._normalize_narrative_lines(narrative_buffer)
            narrative_buffer = []
            if not normalized:
                return
            output.append(cls._format_narrative_block(filename, last_heading, normalized))
            stats["narrative_blocks"] += 1

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                if cls._wordish_len("".join(narrative_buffer)) >= 180:
                    flush_narrative()
                i += 1
                continue

            if cls._is_low_info_text(line) or cls._is_standalone_noise_line(line):
                flush_narrative()
                noise_buffer.append(cls._clean_inline_text(line) or line)
                if len(noise_buffer) >= MAX_NOISE_ITEMS:
                    flush_noise()
                i += 1
                continue

            image_match = IMAGE_RE.fullmatch(line)
            if image_match:
                flush_narrative()
                flush_noise()
                pending_images.append(image_match.group(1))
                stats["image_placeholders"] += 1
                i += 1
                continue

            heading = HEADING_RE.match(line)
            if heading:
                flush_narrative()
                flush_noise()
                title = cls._clean_heading_text(heading.group(2).strip())
                last_heading = title
                recent_context = []
                remember_context(title)
                if pending_images:
                    output.append(cls._format_image_context(filename, last_heading, pending_images, []))
                    pending_images = []

                if cls._is_short_heading(title):
                    body: list[str] = []
                    j = i + 1
                    while j < len(lines):
                        nxt = lines[j].strip()
                        if not nxt:
                            j += 1
                            if body:
                                break
                            continue
                        nxt_image = IMAGE_RE.fullmatch(nxt)
                        if nxt_image:
                            pending_images.append(nxt_image.group(1))
                            stats["image_placeholders"] += 1
                            j += 1
                            continue
                        if HEADING_RE.match(nxt) or "<table" in nxt.lower():
                            break
                        if cls._is_low_info_text(nxt) or cls._is_standalone_noise_line(nxt):
                            noise_buffer.append(cls._clean_inline_text(nxt) or nxt)
                            j += 1
                            continue
                        body.append(nxt)
                        remember_context(nxt)
                        j += 1
                        if cls._wordish_len("".join(body)) >= 260:
                            break
                    consumed_visuals = bool(pending_images)
                    if pending_images:
                        output.append(cls._format_image_context(filename, last_heading, pending_images, body[:3]))
                        pending_images = []
                    if body:
                        output.append(cls._format_fact_block(title, body))
                        stats["short_heading_merges"] += 1
                        i = j
                        continue
                    if consumed_visuals and j > i + 1:
                        output.append(cls._format_topic_context(title, filename))
                        i = j
                        continue

                output.append(cls._format_topic_context(title, filename))
                i += 1
                continue

            if "<table" in line.lower():
                flush_narrative()
                flush_noise()
                table_blob = [line]
                j = i + 1
                while j < len(lines) and "</table>" not in table_blob[-1].lower():
                    table_blob.append(lines[j].strip())
                    j += 1
                output.append(cls._format_table_context_block(filename, last_heading, "".join(table_blob), list(recent_context), lines[j : j + 4]))
                stats["tables_normalized"] += 1
                i = max(j, i + 1)
                continue

            if pending_images:
                flush_narrative()
                flush_noise()
                output.append(cls._format_image_context(filename, last_heading, pending_images, [line]))
                pending_images = []
                remember_context(line)
                i += 1
                continue

            narrative_buffer.append(line)
            remember_context(line)
            if cls._wordish_len("".join(narrative_buffer)) >= MAX_NARRATIVE_CHARS:
                flush_narrative()
            i += 1

        flush_narrative()
        flush_noise()
        if pending_images:
            output.append(cls._format_image_context(filename, last_heading, pending_images, []))
        return cls._collapse_blank_lines("\n\n".join(output)), stats

    @classmethod
    def _build_visual_sections(cls, layout_blocks: list[dict[str, Any]], filename: str) -> list[str]:
        sections: list[str] = []
        recent_heading = ""
        recent_text: list[str] = []
        visual_index = 1
        for block in layout_blocks:
            item_type = str(block.get("type") or "").lower()
            text = str(block.get("text") or "").strip()
            caption = str(block.get("caption") or "").strip()
            page = block.get("page") or ""
            if item_type in {"title", "heading"} or text.startswith("#"):
                recent_heading = cls._clean_heading_text(text.lstrip("# ").strip()) or recent_heading
                continue
            if text and item_type not in {"image", "figure", "picture", "table", "chart"}:
                recent_text.append(cls._clean_inline_text(text))
                recent_text = [item for item in recent_text if item][-4:]
                continue

            if item_type not in {"image", "figure", "picture", "table", "chart"}:
                continue

            visible = cls._clean_inline_text(text or caption)
            title = recent_heading or str(block.get("heading") or "").strip() or "邻近上下文"
            context = "；".join(t for t in recent_text[-2:] if t)
            visual_kind = cls._classify_visual_asset(item_type, visible, title, context)
            if cls._is_low_value_visual(item_type, visible, context, title):
                continue
            source = f"{filename}，第{page}页" if page else filename
            bbox = block.get("bbox") or ""
            lines = [
                f"来源：{source}，视觉元素 {visual_index}",
                f"图像类型：{visual_kind}",
                f"可见文字：{visible or '未提供独立可见文字，使用相邻标题和正文建立上下文。'}",
            ]
            if context:
                lines.append(f"上下文：{context}")
            if bbox:
                lines.append(f"位置：{bbox}")
            lines.append("结构化信息：该视觉元素已绑定来源、页码/幻灯片、位置和邻近正文；普通业务问答只在其包含事实时使用，图片/Logo/海报类问题可作为素材依据。")
            sections.append(cls._format_summary_block("visual_asset", f"图像说明｜{('第' + str(page) + '页｜') if page else ''}{title}", lines))
            visual_index += 1
        return sections[:80]

    @classmethod
    def _format_fact_block(cls, title: str, body: list[str]) -> str:
        role = ROLE_HEADING_RE.match(f"## {title}")
        joined = " ".join(cls._clean_inline_text(part) for part in body if part.strip())
        if cls._is_low_info_text(" ".join([title, joined])):
            return cls._format_noise_block(" ".join([title, joined]), "")
        lines = [f"相关主题：{cls._related_topics_from_text(title + ' ' + joined)}", f"结构化信息：{title + '。' if role else ''}{joined}"]
        return cls._format_summary_block("business_fact", f"主题：{title}", lines)

    @staticmethod
    def _format_topic_context(title: str, filename: str = "") -> str:
        title = title.strip() or "邻近上下文"
        source = f"来源：{filename}，章节/邻近标题：{title}" if filename else f"章节/邻近标题：{title}"
        return MmbVisualDocumentStructurerTool._format_summary_block(
            "narrative_context",
            f"主题上下文｜{title}",
            [source, f"主题说明：{title}。该标题已并入结构化上下文，避免通用分段产生孤立标题段。"],
        )

    @staticmethod
    def _format_image_context(filename: str, heading: str, urls: list[str], body: list[str]) -> str:
        heading = heading or "邻近上下文"
        context = " ".join(part.strip() for part in body if part.strip()) or "该图片附近暂无可抽取正文。"
        preview = "; ".join(urls[:3])
        return MmbVisualDocumentStructurerTool._format_summary_block(
            "visual_asset",
            f"图像说明｜{heading}",
            [
                f"来源：{filename}，章节/邻近标题：{heading}",
                "图像类型：PDF/PPT 内嵌图片或图示",
                f"上下文：{context}",
                f"图片链接：{preview}",
                "结构化信息：图片已绑定邻近标题和正文；回答时优先使用上下文文字，不把裸图片链接作为主要证据。",
            ],
        )

    @classmethod
    def _clean_tables(cls, text: str) -> str:
        text = re.sub(r"<td\s*rowspan", "<td rowspan", text, flags=re.I)
        text = re.sub(r"<td\s*colspan", "<td colspan", text, flags=re.I)
        text = re.sub(r"rowspan=([^ >]+)colspan", r"rowspan=\1 colspan", text, flags=re.I)
        text = re.sub(r"rowspan=([^ >]+)\s+colspan", r"rowspan=\1 colspan", text, flags=re.I)
        text = re.sub(r"<tdrowspan", "<td rowspan", text, flags=re.I)
        text = re.sub(r"<tdcolspan", "<td colspan", text, flags=re.I)
        text = re.sub(r"</td><tdrowspan", "</td><td rowspan", text, flags=re.I)
        return text

    @classmethod
    def _format_table_context_block(cls, filename: str, heading: str, html: str, previous_blocks: list[str], next_lines: list[str]) -> str:
        table = cls._parse_html_table(html)
        if not table:
            table_text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            return cls._format_summary_block(
                "table_fact",
                f"表格事实｜{heading or '邻近上下文'}",
                [
                    f"来源：{filename}，章节/邻近标题：{heading or '邻近上下文'}",
                    f"相关主题：{cls._table_related_topics(heading, [], [])}",
                    f"表格摘要：该表格来自 {heading or filename}，原始结构未能完整识别，已保留可见文本用于检索。",
                    f"表格可见文字：{table_text}",
                ],
            )

        header, rows = table
        markdown = cls._table_to_markdown(header, rows)
        facts = cls._table_rows_to_facts(header, rows)
        context = cls._table_context_text(previous_blocks, next_lines)
        summary = cls._summarize_table(heading, header, rows, context)
        title_parts = ["表格事实"]
        if heading:
            title_parts.append(heading)
        lines = [
            f"来源：{filename}，章节/邻近标题：{heading or '邻近上下文'}",
            f"相关主题：{cls._table_related_topics(heading, header, rows, context)}",
        ]
        if context:
            lines.append(f"上下文：{context}")
        lines.extend([f"表格摘要：{summary}", markdown])
        if facts:
            lines.extend(["表格事实展开：", *facts])
        return cls._format_summary_block("table_fact", "｜".join(title_parts), lines)

    @classmethod
    def _parse_html_table(cls, html: str) -> tuple[list[str], list[list[str]]] | None:
        soup = BeautifulSoup(html, "html.parser")
        grid: list[list[str]] = []
        rowspans: dict[tuple[int, int], str] = {}
        for row_index, tr in enumerate(soup.find_all("tr")):
            row: list[str] = []
            col_index = 0
            for cell in tr.find_all(["th", "td"]):
                while (row_index, col_index) in rowspans:
                    row.append(rowspans.pop((row_index, col_index)))
                    col_index += 1
                text = cls._clean_table_cell(cell.get_text(" ", strip=True))
                try:
                    rowspan = max(int(cell.get("rowspan") or 1), 1)
                except Exception:
                    rowspan = 1
                try:
                    colspan = max(int(cell.get("colspan") or 1), 1)
                except Exception:
                    colspan = 1
                for offset in range(colspan):
                    row.append(text)
                    if rowspan > 1:
                        for span_row in range(1, rowspan):
                            rowspans[(row_index + span_row, col_index + offset)] = text
                col_index += colspan
            while (row_index, col_index) in rowspans:
                row.append(rowspans.pop((row_index, col_index)))
                col_index += 1
            if any(row):
                grid.append(row)
        if not grid:
            return None
        width = max(len(row) for row in grid)
        padded_rows = [row + [""] * (width - len(row)) for row in grid]
        return padded_rows[0], padded_rows[1:]

    @classmethod
    def _html_table_to_markdown(cls, html: str) -> str:
        table = cls._parse_html_table(html)
        if table is None:
            return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        header, body = table
        md = [cls._table_to_markdown(header, body)]
        facts = cls._table_rows_to_facts(header, body)
        if facts:
            md.extend(["", "表格事实展开：", *facts])
        return "\n".join(md)

    @staticmethod
    def _table_to_markdown(header: list[str], body: list[list[str]]) -> str:
        width = len(header)
        md = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
        md.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(md)

    @classmethod
    def _table_rows_to_facts(cls, header: list[str], body: list[list[str]]) -> list[str]:
        facts = []
        for row in body[:12]:
            pairs = [f"{header[i]}: {row[i]}" for i in range(min(len(header), len(row))) if header[i] and row[i]]
            if pairs:
                facts.append("- " + cls._fact_sentence_from_pairs(header, row, pairs))
        return facts

    @staticmethod
    def _fact_sentence_from_pairs(header: list[str], row: list[str], pairs: list[str]) -> str:
        normalized = {h.strip(): row[i].strip() for i, h in enumerate(header[: len(row)]) if h.strip() and row[i].strip()}
        if not pairs:
            pairs = [f"{key}: {value}" for key, value in normalized.items()]
        role = next((normalized[key] for key in normalized if any(word in key for word in ("岗位", "职位", "角色", "职责", "分工"))), "")
        name = next((normalized[key] for key in normalized if any(word in key for word in ("姓名", "人员", "成员", "负责人", "参与人", "名称"))), "")
        note = next((normalized[key] for key in normalized if any(word in key for word in ("备注", "说明", "工作", "内容", "职责", "任务"))), "")
        if role and name and note:
            return f"{role}：{name}，{note}。"
        if role and name:
            return f"{role}：{name}。"
        return "；".join(pairs)

    @classmethod
    def _table_context_text(cls, previous_blocks: list[str], next_lines: list[str]) -> str:
        candidates: list[str] = []
        for block in previous_blocks[-5:]:
            cleaned = cls._clean_inline_text(block)
            if cleaned and not cls._is_low_info_text(cleaned) and not cls._is_context_noise_text(cleaned):
                candidates.append(cleaned[:180])
        for line in next_lines[:3]:
            if HEADING_RE.match(line.strip()):
                break
            cleaned = cls._clean_inline_text(line)
            if cleaned and not cls._is_low_info_text(cleaned) and not cls._is_context_noise_text(cleaned):
                candidates.append(cleaned[:140])
        deduped: list[str] = []
        for item in candidates:
            if item and item not in deduped:
                deduped.append(item)
        return "；".join(deduped[-4:])[:520]

    @classmethod
    def _summarize_table(cls, heading: str, header: list[str], rows: list[list[str]], context: str) -> str:
        subject = heading or context or "当前文档"
        row_summaries: list[str] = []
        for row in rows[:12]:
            fact = cls._fact_sentence_from_pairs(header, row, [])
            row_summaries.append(fact.rstrip("。"))
        if row_summaries:
            return f"本表记录{subject}相关信息，包括" + "、".join(row_summaries) + "。"
        columns = "、".join(h for h in header if h)
        return f"本表记录{subject}相关信息，字段包括{columns}。"

    @classmethod
    def _table_related_topics(cls, heading: str, header: list[str], rows: list[list[str]], context: str = "") -> str:
        topics: list[str] = []
        source = " ".join([heading, context, " ".join(header), " ".join(" ".join(row) for row in rows[:6])])
        if any(key in source for key in ("团队", "组织架构", "职责", "岗位", "人员", "成员", "负责人")):
            topics.extend(["团队组织架构", "职责分工", "参与人员", "团队成员", "负责人"])
        if any(key in source for key in ("技术", "小程序", "开发", "全站", "UI", "硬件")):
            topics.extend(["技术会议人员", "小程序开发团队", "技术团队", "开发分工"])
        if any(key in source for key in ("加盟", "合伙", "投资", "分红", "权益", "档位")):
            topics.extend(["加盟方式", "合作模式", "投资档位", "分红权益"])
        topics.extend(cls._topic_tokens(source))
        lowered = source.lower()
        if "mmb" in lowered or any(key in source for key in ("瞢瞢熊", "麦乐迪", "鲜啤")):
            topics.extend(["MMB", "瞢瞢熊", "麦乐迪智慧鲜啤交易所"])
        deduped: list[str] = []
        for topic in topics:
            if topic and topic not in deduped and not cls._is_context_noise_text(topic):
                deduped.append(topic)
        return "、".join(deduped[:24]) or "表格信息、结构化事实、业务资料"

    @classmethod
    def _build_layout_ir(cls, content_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        heading_path: list[str] = []
        for index, item in enumerate(content_list):
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or item.get("category") or item.get("block_type") or item.get("kind") or "text").lower()
            text = cls._extract_item_text(item)
            caption = cls._extract_caption(item)
            page = cls._extract_page(item)
            bbox = item.get("bbox") or item.get("poly") or item.get("position") or ""
            if item_type in {"title", "heading"} or text.startswith("#"):
                title = cls._clean_heading_text(text.lstrip("# ").strip())
                if title:
                    level = 1
                    level_value = item.get("level") or item.get("heading_level")
                    try:
                        level = max(min(int(level_value), 6), 1) if level_value else 1
                    except Exception:
                        level = 1
                    heading_path = heading_path[: level - 1] + [title]
            blocks.append(
                {
                    "order": index,
                    "type": item_type,
                    "text": text,
                    "caption": caption,
                    "page": page,
                    "bbox": bbox,
                    "heading": " / ".join(heading_path),
                    "raw": item,
                }
            )
        return blocks

    @classmethod
    def _format_narrative_block(cls, filename: str, heading: str, lines: list[str]) -> str:
        heading = heading or "正文上下文"
        body = " ".join(lines)
        return cls._format_summary_block(
            "narrative_context",
            f"正文事实｜{heading}",
            [
                f"来源：{filename}，章节/邻近标题：{heading}",
                f"相关主题：{cls._related_topics_from_text(heading + ' ' + body)}",
                f"正文内容：{body}",
            ],
        )

    @classmethod
    def _normalize_narrative_lines(cls, lines: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in lines:
            line = cls._clean_inline_text(raw)
            if not line or cls._is_low_info_text(line) or cls._is_standalone_noise_line(line):
                continue
            if IMAGE_RE.fullmatch(line) or RAW_URL_RE.fullmatch(line):
                continue
            normalized.append(line[:260])
        return normalized

    @classmethod
    def _related_topics_from_text(cls, text: str) -> str:
        topics: list[str] = []
        if any(key in text for key in ("团队", "创始", "负责人", "人员", "职责")):
            topics.extend(["核心团队", "创始人", "负责人", "职责分工"])
        if any(key in text for key in ("深圳文交所", "深圳文化产权交易所", "深文所", "战略合作", "合作")):
            topics.extend(["深圳文交所合作", "战略合作", "合作内容"])
        if any(key in text for key in ("加盟", "合伙", "代理", "投资", "分润", "收益")):
            topics.extend(["加盟方式", "合作模式", "投资合作", "分润收益"])
        if any(key in text for key in ("融资", "天使轮", "A轮", "B轮", "估值", "退出")):
            topics.extend(["融资方案", "轮次", "估值", "退出路径"])
        if any(key in text for key in ("产品", "参数", "小程序", "售货机", "设备", "鲜啤")):
            topics.extend(["产品参数", "小程序", "设备", "智慧鲜啤"])
        topics.extend(cls._topic_tokens(text))
        deduped: list[str] = []
        for topic in topics:
            if topic and topic not in deduped and not cls._is_context_noise_text(topic):
                deduped.append(topic)
        return "、".join(deduped[:18]) or "业务资料、正文上下文"

    @classmethod
    def _topic_tokens(cls, text: str) -> list[str]:
        tokens: list[str] = []
        for token in re.split(r"[\s,，。;；|/\\:：()（）\[\]【】<>《》]+", text):
            token = token.strip("#*-_ ")
            if cls._wordish_len(token) < 2 or cls._wordish_len(token) > 32:
                continue
            if cls._is_low_info_text(token) or cls._is_context_noise_text(token) or RAW_URL_RE.match(token):
                continue
            if token.lower() in {"http", "https", "files", "source", "chunk_type", "visual_asset"}:
                continue
            tokens.append(token)
        return tokens[:30]

    @staticmethod
    def _clean_table_cell(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        text = text.replace("|", "/")
        return text

    @staticmethod
    def _clean_heading_text(text: str) -> str:
        text = re.sub(r"[*_`]+", "", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:120]

    @staticmethod
    def _clean_inline_text(text: str) -> str:
        text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
        text = re.sub(r"<!--.*?-->", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _is_standalone_noise_line(cls, text: str) -> bool:
        cleaned = cls._clean_inline_text(text)
        if not cleaned:
            return False
        lowered = cleaned.lower().strip()
        if PUNCT_ONLY_RE.fullmatch(cleaned):
            return True
        if RAW_URL_RE.fullmatch(cleaned):
            return True
        if re.fullmatch(r"(?:第?\s*\d+\s*(?:页|page)?)", lowered, re.I):
            return True
        if re.fullmatch(r"阅读\d+赞\d+.*", cleaned):
            return True
        if cleaned in UI_NOISE_TERMS:
            return True
        compact = cls._wordish_len(cleaned)
        if compact <= 1:
            return True
        if compact <= 3 and cleaned not in SIGNIFICANT_SHORT_TERMS:
            return True
        return False

    @classmethod
    def _is_context_noise_text(cls, text: str) -> bool:
        cleaned = cls._clean_inline_text(text)
        if not cleaned:
            return True
        if TYPED_CHUNK_RE.search(cleaned):
            return True
        if any(cleaned.startswith(prefix) for prefix in SOURCE_META_PREFIXES):
            return True
        lowered = cleaned.lower()
        if "图片链接" in cleaned or "image-preview" in lowered or "files/tools" in lowered:
            return True
        if "该主题的标题已并入正文" in cleaned or "避免通用分段产生孤立标题段" in cleaned:
            return True
        return False

    @classmethod
    def _classify_visual_asset(cls, item_type: str, visible: str, title: str, context: str) -> str:
        source = " ".join([item_type, visible, title, context]).lower()
        if "logo" in source or "标识" in source:
            return "Logo/合作标识"
        if any(key in source for key in ("海报", "poster", "宣传", "活动")):
            return "海报/宣传页"
        if any(key in source for key in ("团队", "创始", "负责人", "ceo", "cto", "cfo")):
            return "人物/团队介绍"
        if any(key in source for key in ("图表", "表格", "chart", "table", "趋势", "数据")):
            return "图表/表格"
        if any(key in source for key in ("产品", "设备", "机器", "小程序", "鲜啤")):
            return "产品/业务场景"
        return "图片/图示"

    @classmethod
    def _is_low_value_visual(cls, item_type: str, visible: str, context: str, title: str) -> bool:
        source = " ".join([visible, context, title])
        if item_type == "table" and cls._wordish_len(source) < 8:
            return True
        if not visible and not context:
            return True
        if cls._is_low_info_text(source) and cls._wordish_len(context) < 8:
            return True
        return False

    @classmethod
    def _quality_gate(cls, output: str, stats: dict[str, int]) -> dict[str, Any]:
        typed_counts: dict[str, int] = {}
        for match in TYPED_CHUNK_RE.finditer(output):
            chunk_type = match.group(1).lower()
            typed_counts[chunk_type] = typed_counts.get(chunk_type, 0) + 1
        untyped_short_lines = []
        for raw in output.splitlines():
            line = raw.strip()
            if not line or TYPED_CHUNK_RE.search(line) or line.startswith(("###", "|", "-")):
                continue
            if cls._wordish_len(line) < 30 and not any(line.startswith(prefix) for prefix in ("来源：", "相关主题：", "图像类型：", "可见文字：")):
                untyped_short_lines.append(line)
        naked_links = [line for line in output.splitlines() if IMAGE_RE.fullmatch(line.strip()) or RAW_URL_RE.fullmatch(line.strip())]
        passed = len(untyped_short_lines) <= 3 and not naked_links and bool(typed_counts)
        return {
            "passed": passed,
            "status": "passed" if passed else "strong_clean_retry_needed",
            "typed_chunk_counts": typed_counts,
            "untyped_short_line_count": len(untyped_short_lines),
            "naked_link_count": len(naked_links),
            "quality_retry": stats.get("quality_retry", 0),
        }

    @classmethod
    def _force_type_short_fragments(cls, output: str, filename: str) -> str:
        fixed: list[str] = []
        loose: list[str] = []
        in_typed_block = False
        for line in output.splitlines():
            stripped = line.strip()
            if TYPED_CHUNK_RE.search(stripped):
                in_typed_block = True
            elif not stripped:
                in_typed_block = False
            if (
                stripped
                and not in_typed_block
                and not stripped.startswith("|")
                and not TYPED_CHUNK_RE.search(stripped)
                and cls._wordish_len(stripped) < 30
                and cls._is_standalone_noise_line(stripped)
            ):
                loose.append(stripped)
                continue
            if loose:
                fixed.append(cls._format_noise_block("\n".join(f"- {item}" for item in loose), filename))
                loose = []
            fixed.append(line)
        if loose:
            fixed.append(cls._format_noise_block("\n".join(f"- {item}" for item in loose), filename))
        return cls._collapse_blank_lines("\n".join(fixed)) + "\n"

    @staticmethod
    def _is_short_heading(title: str) -> bool:
        if ROLE_HEADING_RE.match(f"## {title}"):
            return True
        return len(title) <= 32 and any(key in title for key in ("创始", "創始", "负责人", "負責人", "团队", "團隊", "融资", "参数", "产品", "合作", "加盟", "投资"))

    @classmethod
    def _format_summary_block(cls, chunk_type: str, title: str, lines: list[str]) -> str:
        body = [line.strip() for line in lines if line and line.strip()]
        return "\n".join([f"<!-- chunk_type: {chunk_type} -->", f"### {title}", *body])

    @classmethod
    def _format_noise_block(cls, text: str, filename: str) -> str:
        source = f"来源：{filename}" if filename else "来源：当前文档"
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cls._format_summary_block(
            "ocr_noise",
            "低信息 OCR/Logo 文本",
            [source, f"原始文本：{cleaned}", "用途：仅作为视觉素材辅助信息，普通业务问答不应使用本段作为主要依据。"],
        )

    @classmethod
    def _is_low_info_text(cls, text: str) -> bool:
        cleaned = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        cleaned = re.sub(r"^[#>*\-\s]+", "", cleaned).strip()
        cleaned = re.sub(r"[\s:：,，。;；|/\\_\-]+", " ", cleaned).strip()
        if not cleaned:
            return False
        lowered = cleaned.lower()
        if lowered in LOW_INFO_TERMS or cleaned in UI_NOISE_TERMS:
            return True
        if PUNCT_ONLY_RE.fullmatch(cleaned):
            return True
        if re.fullmatch(r"(?:第?\s*\d+\s*(?:页|page)?|\d+/\d+)", lowered, re.I):
            return True
        if re.fullmatch(r"阅读\d+赞\d+.*", cleaned):
            return True
        tokens = [token for token in re.split(r"\s+", lowered) if token]
        if 0 < len(tokens) <= 3 and all(token in LOW_INFO_TERMS for token in tokens):
            return True
        if re.fullmatch(r"(?:ocr文字|ocr 文本|logo|品牌logo)\s*(?:mmb)?", lowered, re.I):
            return True
        if cls._wordish_len(cleaned) <= 2 and cleaned not in SIGNIFICANT_SHORT_TERMS:
            return True
        return False

    @staticmethod
    def _wordish_len(text: str) -> int:
        return len(re.sub(r"\s+", "", text))

    @staticmethod
    def _extract_item_text(item: dict[str, Any]) -> str:
        for key in ("text", "content", "md", "html", "caption", "img_caption"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        return ""

    @staticmethod
    def _extract_caption(item: dict[str, Any]) -> str:
        for key in ("caption", "img_caption", "image_caption", "description"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                return "；".join(str(v).strip() for v in value if str(v).strip())
        return ""

    @staticmethod
    def _extract_page(item: dict[str, Any]) -> Any:
        for key in ("page_idx", "page", "page_no", "slide", "slide_no"):
            if key in item and item[key] not in (None, ""):
                try:
                    return int(item[key]) + 1 if key == "page_idx" else item[key]
                except Exception:
                    return item[key]
        return ""

    @staticmethod
    def _metadata_from_text(text: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for line in text.splitlines()[:40]:
            match = re.match(r"-\s*([A-Za-z0-9_]+):\s*(.+)$", line.strip())
            if match:
                metadata[match.group(1)] = match.group(2)
        return metadata

    @classmethod
    def _parse_jsonish(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, (dict, list)):
            return value
        text = cls._as_text(value).strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _collapse_blank_lines(text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text).strip()
