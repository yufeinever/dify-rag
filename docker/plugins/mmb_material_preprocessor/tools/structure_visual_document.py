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

BRAND_ALIASES = "MMB、瞢瞢熊、懵懵熊、麦乐迪智慧鲜啤交易所"
LOW_INFO_TERMS = {
    "mmb",
    "瞢瞢熊",
    "懵懵熊",
    "麦乐迪",
    "智慧鲜啤",
    "麦乐迪智慧鲜啤交易所",
}
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

        cleaned_text = self._clean_tables(self._strip_normalize_preamble(parsed_text))
        structured_body, stats = self._structure_markdown(cleaned_text, filename)
        key_fact_sections = self._build_topic_fact_sections(cleaned_text, filename)
        visual_sections = self._build_visual_sections(content_list, filename)

        report = {
            "parser": "mmb-visual-document-structurer",
            "source_file_name": filename,
            "file_extension": extension,
            "content_items": len(content_list),
            "visual_sections": len(visual_sections),
            "short_heading_merges": stats["short_heading_merges"],
            "image_placeholders": stats["image_placeholders"],
            "tables_normalized": stats["tables_normalized"],
            "noise_blocks_marked": stats["noise_blocks_marked"],
            "topic_fact_sections": len(key_fact_sections),
            "strategy": "mineru_markdown_visual_context_binding_general_chunker_input",
        }

        output_parts: list[str] = []
        if key_fact_sections:
            output_parts.extend(key_fact_sections + [""])
        if visual_sections:
            output_parts.extend(visual_sections + [""])
        output_parts.extend([structured_body.strip(), ""])
        output = "\n".join(output_parts).strip() + "\n"

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
    def _structure_markdown(cls, text: str, filename: str) -> tuple[str, dict[str, int]]:
        lines = [line.rstrip() for line in text.splitlines()]
        output: list[str] = []
        stats = {"short_heading_merges": 0, "image_placeholders": 0, "tables_normalized": 0, "noise_blocks_marked": 0}
        pending_images: list[str] = []
        last_heading = ""
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            if not line:
                i += 1
                continue
            if cls._is_low_info_text(line):
                output.append(cls._format_noise_block(line, filename))
                stats["noise_blocks_marked"] += 1
                i += 1
                continue

            image_match = IMAGE_RE.fullmatch(line)
            if image_match:
                pending_images.append(image_match.group(1))
                stats["image_placeholders"] += 1
                i += 1
                continue

            heading = HEADING_RE.match(line)
            if heading:
                title = heading.group(2).strip()
                last_heading = title
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
                        body.append(nxt)
                        j += 1
                        if cls._wordish_len("".join(body)) >= 220:
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
                        output.append(cls._format_topic_context(title))
                        i = j
                        continue

                output.append(cls._format_topic_context(title))
                i += 1
                continue

            if "<table" in line.lower():
                table_blob = [line]
                j = i + 1
                while j < len(lines) and "</table>" not in table_blob[-1].lower():
                    table_blob.append(lines[j].strip())
                    j += 1
                output.append(cls._format_table_context_block(filename, last_heading, "".join(table_blob), output[-3:], lines[j : j + 3]))
                stats["tables_normalized"] += 1
                i = max(j, i + 1)
                continue

            if pending_images:
                output.append(cls._format_image_context(filename, last_heading, pending_images, [line]))
                pending_images = []
            output.append(line)
            i += 1

        if pending_images:
            output.append(cls._format_image_context(filename, last_heading, pending_images, []))
        return cls._collapse_blank_lines("\n\n".join(output)), stats

    @classmethod
    def _build_visual_sections(cls, content_list: list[dict[str, Any]], filename: str) -> list[str]:
        sections: list[str] = []
        recent_heading = ""
        recent_text: list[str] = []
        visual_index = 1
        for item in content_list:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or item.get("category") or item.get("block_type") or "").lower()
            text = cls._extract_item_text(item)
            page = cls._extract_page(item)
            if item_type in {"title", "heading"} or text.startswith("#"):
                recent_heading = text.lstrip("# ").strip() or recent_heading
            elif text and item_type not in {"image", "figure", "picture"}:
                recent_text.append(text)
                recent_text = recent_text[-4:]

            if item_type not in {"image", "figure", "picture", "table"}:
                continue

            kind = "表格/图表" if item_type == "table" else "图片/图示"
            visible = text or cls._extract_caption(item) or "未提供独立可见文字，使用相邻标题和正文建立上下文。"
            source = f"{filename}，第{page}页" if page else filename
            title = recent_heading or "邻近上下文"
            context = "；".join(t for t in recent_text[-2:] if t)
            bbox = item.get("bbox") or item.get("poly") or item.get("position") or ""
            lines = [
                f"### 图像说明｜{('第' + str(page) + '页｜') if page else ''}{title}",
                f"来源：{source}，视觉元素 {visual_index}",
                f"图像类型：{kind}",
                f"可见文字：{visible}",
            ]
            if context:
                lines.append(f"上下文：{context}")
            if bbox:
                lines.append(f"位置：{bbox}")
            lines.append("结构化信息：该视觉元素已绑定来源、页码/上下文和邻近正文，用于 PDF/PPT 图文检索。")
            sections.append(cls._format_summary_block("visual_asset", "视觉元素标注", lines))
            visual_index += 1
        return sections[:80]

    @classmethod
    def _format_fact_block(cls, title: str, body: list[str]) -> str:
        role = ROLE_HEADING_RE.match(f"## {title}")
        joined = " ".join(part.strip() for part in body if part.strip())
        if cls._is_low_info_text(" ".join([title, joined])):
            return cls._format_noise_block(" ".join([title, joined]), "")
        if role:
            return cls._format_summary_block("business_fact", f"主题：{title}", [f"结构化信息：{title}。{joined}"])
        return cls._format_summary_block("business_fact", f"主题：{title}", [f"结构化信息：{joined}"])

    @staticmethod
    def _format_topic_context(title: str) -> str:
        title = title.strip() or "邻近上下文"
        return f"主题：{title}。该主题的标题已并入正文，避免通用分段产生孤立标题段。"

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

    @staticmethod
    def _parse_html_table(html: str) -> tuple[list[str], list[list[str]]] | None:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[list[str]] = []
        for tr in soup.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        if not rows:
            return None
        width = max(len(row) for row in rows)
        padded_rows = [row + [""] * (width - len(row)) for row in rows]
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
        for block in previous_blocks[-3:]:
            text = BeautifulSoup(block, "html.parser").get_text(" ", strip=True)
            text = re.sub(r"<!--.*?-->", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            if text and not cls._is_low_info_text(text):
                candidates.append(text[:180])
        for line in next_lines[:2]:
            text = BeautifulSoup(line.strip(), "html.parser").get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text and not HEADING_RE.match(line.strip()) and not cls._is_low_info_text(text):
                candidates.append(text[:120])
        return "；".join(candidates[-3:])[:420]

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
        for token in re.split(r"[\s,，。;；|/\\:：()（）\[\]【】]+", source):
            token = token.strip("#*- ")
            if cls._wordish_len(token) >= 2 and not cls._is_low_info_text(token) and token not in topics:
                topics.append(token)
        lowered = source.lower()
        if "mmb" in lowered or any(key in source for key in ("瞢瞢熊", "麦乐迪", "鲜啤")):
            topics.extend(["MMB", "瞢瞢熊", "麦乐迪智慧鲜啤交易所"])
        deduped: list[str] = []
        for topic in topics:
            if topic and topic not in deduped:
                deduped.append(topic)
        return "、".join(deduped[:24]) or "表格信息、结构化事实、业务资料"

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
        if lowered in LOW_INFO_TERMS:
            return True
        tokens = [token for token in re.split(r"\s+", lowered) if token]
        if 0 < len(tokens) <= 3 and all(token in LOW_INFO_TERMS for token in tokens):
            return True
        if re.fullmatch(r"(?:ocr文字|ocr 文本|logo|品牌logo)\s*(?:mmb)?", lowered, re.I):
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
