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
        key_fact_sections = self._build_key_fact_sections(cleaned_text, filename)
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
            "strategy": "mineru_markdown_visual_context_binding_general_chunker_input",
        }

        header = [
            "MMB PDF/PPT 图文结构化增强：以下内容已完成视觉元素标注、页码来源绑定和结构化正文整理。",
            f"- source_file_name: {filename}",
            f"- parser: {report['parser']}",
            "- chunking_target: text_model_general_chunker",
            "- rule: 内嵌图片/图表必须绑定页码、标题和邻近上下文；禁止裸图片链接作为主要入库内容。",
            "",
        ]
        output_parts = header
        if key_fact_sections:
            output_parts.extend(["关键事实摘要：以下高价值事实已合并为问答友好的完整段落。", "", *key_fact_sections, ""])
        if visual_sections:
            output_parts.extend(["视觉元素标注：以下图像/图表说明已绑定页码、标题和邻近上下文。", "", *visual_sections, ""])
        output_parts.extend(["结构化正文：以下正文已合并短标题、清洗表格并保留来源上下文。", "", structured_body.strip(), ""])
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
    def _build_key_fact_sections(cls, text: str, filename: str) -> list[str]:
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
        if not team_members:
            return []
        return [
            "核心团队成员汇总：" + "；".join(team_members) + f"。来源：{filename}，核心团队页面/邻近章节。"
        ]

    @classmethod
    def _structure_markdown(cls, text: str, filename: str) -> tuple[str, dict[str, int]]:
        lines = [line.rstrip() for line in text.splitlines()]
        output: list[str] = []
        stats = {"short_heading_merges": 0, "image_placeholders": 0, "tables_normalized": 0}
        pending_images: list[str] = []
        last_heading = ""
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            if not line:
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
                output.append(cls._html_table_to_markdown("".join(table_blob)))
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
            sections.append("\n".join(lines))
            visual_index += 1
        return sections[:80]

    @staticmethod
    def _format_fact_block(title: str, body: list[str]) -> str:
        role = ROLE_HEADING_RE.match(f"## {title}")
        joined = " ".join(part.strip() for part in body if part.strip())
        if role:
            return f"主题：{title}\n结构化信息：{title}。{joined}"
        return f"主题：{title}\n结构化信息：{joined}"

    @staticmethod
    def _format_topic_context(title: str) -> str:
        title = title.strip() or "邻近上下文"
        return f"主题：{title}。该主题的标题已并入正文，避免通用分段产生孤立标题段。"

    @staticmethod
    def _format_image_context(filename: str, heading: str, urls: list[str], body: list[str]) -> str:
        heading = heading or "邻近上下文"
        context = " ".join(part.strip() for part in body if part.strip()) or "该图片附近暂无可抽取正文。"
        preview = "; ".join(urls[:3])
        return "\n".join(
            [
                f"### 图像说明｜{heading}",
                f"来源：{filename}，章节/邻近标题：{heading}",
                "图像类型：PDF/PPT 内嵌图片或图示",
                f"上下文：{context}",
                f"图片链接：{preview}",
                "结构化信息：图片已绑定邻近标题和正文；回答时优先使用上下文文字，不把裸图片链接作为主要证据。",
            ]
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

    @staticmethod
    def _html_table_to_markdown(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[list[str]] = []
        for tr in soup.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        if not rows:
            return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        header, body = rows[0], rows[1:]
        md = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
        md.extend("| " + " | ".join(row) + " |" for row in body)
        facts = []
        for row in body[:12]:
            pairs = [f"{header[i]}: {row[i]}" for i in range(min(len(header), len(row))) if header[i] and row[i]]
            if pairs:
                facts.append("- " + "；".join(pairs))
        if facts:
            md.extend(["", "表格事实展开：", *facts])
        return "\n".join(md)

    @staticmethod
    def _is_short_heading(title: str) -> bool:
        if ROLE_HEADING_RE.match(f"## {title}"):
            return True
        return len(title) <= 32 and any(key in title for key in ("创始", "創始", "负责人", "負責人", "团队", "團隊", "融资", "参数", "产品"))

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
