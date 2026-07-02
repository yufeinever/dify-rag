from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from .config import Settings


DEFAULT_FACT_EXPANSIONS = {
    "创始人": ["创始人", "创始人：", "创始人:", "创办人", "创办人：", "创始团队", "陈总", "负责人"],
    "创办人": ["创办人", "创办人：", "创始人", "创始人：", "创始团队"],
    "负责人": ["负责人", "创始人", "陈总", "团队"],
    "founder": ["founder", "创始人", "创办人"],
}


class DifyMetadataRepository:
    """Read-only access to Dify metadata and indexed document evidence for the material agent."""

    settings: Settings

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _connect(self):
        import psycopg

        return psycopg.connect(
            host=self.settings.dify_db_host,
            port=self.settings.dify_db_port,
            dbname=self.settings.dify_db_name,
            user=self.settings.dify_db_user,
            password=self.settings.dify_db_password,
            row_factory=dict_row,
        )

    def list_datasets(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id::text,
                        d.name,
                        d.description,
                        d.provider,
                        d.indexing_technique,
                        d.created_at,
                        d.updated_at,
                        COUNT(doc.id) AS document_count,
                        COALESCE(SUM(doc.word_count), 0) AS word_count
                    FROM datasets d
                    LEFT JOIN documents doc ON doc.dataset_id = d.id AND doc.archived = false
                    GROUP BY d.id
                    ORDER BY d.updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_dataset_documents(self, dataset_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH document_sources AS (
                        SELECT
                            doc.*,
                            CASE
                                WHEN (doc.data_source_info::jsonb ->> 'related_id') ~
                                    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                                THEN (doc.data_source_info::jsonb ->> 'related_id')::uuid
                                ELSE NULL
                            END AS related_upload_file_id
                        FROM documents doc
                        WHERE doc.dataset_id = %s::uuid AND doc.archived = false
                    )
                    SELECT
                        ds.id::text AS document_id,
                        ds.name AS document_name,
                        ds.indexing_status,
                        ds.word_count,
                        ds.tokens,
                        ds.created_at,
                        ds.updated_at,
                        ds.completed_at,
                        ds.error,
                        ds.data_source_info,
                        uf.id::text AS upload_file_id,
                        uf.name AS upload_name,
                        uf.key AS upload_key,
                        uf.size AS upload_size,
                        uf.extension AS upload_extension,
                        uf.mime_type AS upload_mime_type,
                        uf.hash AS upload_hash
                    FROM document_sources ds
                    LEFT JOIN upload_files uf ON uf.id = ds.related_upload_file_id
                    ORDER BY ds.updated_at DESC
                    LIMIT %s
                    """,
                    (dataset_id, limit),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_documents(self, dataset_id: str | None = None, query: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["doc.archived = false"]
        params: list[Any] = []
        if dataset_id:
            clauses.append("doc.dataset_id = %s::uuid")
            params.append(dataset_id)
        if query:
            clauses.append("doc.name ILIKE %s")
            params.append(f"%{query}%")
        params.append(limit)
        where_sql = " AND ".join(clauses)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        doc.id::text AS document_id,
                        doc.dataset_id::text AS dataset_id,
                        d.name AS dataset_name,
                        doc.name AS document_name,
                        doc.indexing_status,
                        doc.word_count,
                        doc.tokens,
                        doc.created_at,
                        doc.updated_at
                    FROM documents doc
                    JOIN datasets d ON d.id = doc.dataset_id
                    WHERE {where_sql}
                    ORDER BY doc.updated_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_apps(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        app.id::text,
                        app.name,
                        app.mode,
                        app.created_at,
                        app.updated_at,
                        COALESCE(
                            json_agg(
                                json_build_object('dataset_id', d.id::text, 'dataset_name', d.name)
                                ORDER BY d.updated_at DESC
                            ) FILTER (WHERE d.id IS NOT NULL),
                            '[]'::json
                        ) AS datasets
                    FROM apps app
                    LEFT JOIN app_dataset_joins adj ON adj.app_id = app.id
                    LEFT JOIN datasets d ON d.id = adj.dataset_id
                    GROUP BY app.id
                    ORDER BY app.updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]

    def search_segments(
        self,
        query: str,
        dataset_id: str | None = None,
        document_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        terms = self._expand_query_terms(query)
        if not terms:
            return []
        clauses = ["seg.enabled = true", "seg.status = 'completed'"]
        params: list[Any] = []
        if dataset_id:
            clauses.append("seg.dataset_id = %s::uuid")
            params.append(dataset_id)
        if document_id:
            clauses.append("seg.document_id = %s::uuid")
            params.append(document_id)
        match_sql = " OR ".join(["seg.content ILIKE %s" for _ in terms])
        clauses.append(f"({match_sql})")
        match_patterns = [f"%{term}%" for term in terms]
        params.extend(match_patterns)
        order_score_sql = " + ".join(["CASE WHEN seg.content ILIKE %s THEN 1 ELSE 0 END" for _ in terms])
        fetch_limit = min(max(limit * 50, 100), 500)
        params.extend(match_patterns)
        params.append(fetch_limit)
        where_sql = " AND ".join(clauses)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        seg.id::text AS segment_id,
                        seg.dataset_id::text AS dataset_id,
                        dset.name AS dataset_name,
                        seg.document_id::text AS document_id,
                        doc.name AS document_name,
                        seg.position,
                        seg.content,
                        seg.word_count,
                        seg.tokens,
                        doc.updated_at AS document_updated_at
                    FROM document_segments seg
                    JOIN documents doc ON doc.id = seg.document_id
                    JOIN datasets dset ON dset.id = seg.dataset_id
                    WHERE {where_sql}
                    ORDER BY ({order_score_sql}) DESC, doc.updated_at DESC, seg.position ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = [dict(row) for row in cur.fetchall()]
        ranked = [self._format_segment_hit(row, terms) for row in rows]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return self._dedupe_segment_hits(ranked, min(max(limit, 1), 50))

    def search_upload_files(
        self,
        query: str | None = None,
        extension: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        clauses = ["1 = 1"]
        params: list[Any] = []
        if query:
            clauses.append("(uf.name ILIKE %s OR uf.key ILIKE %s OR uf.source_url ILIKE %s)")
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
        if extension:
            ext = extension[1:] if extension.startswith(".") else extension
            clauses.append("LOWER(uf.extension) = LOWER(%s)")
            params.append(ext)
        params.append(limit)
        where_sql = " AND ".join(clauses)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        uf.id::text AS upload_file_id,
                        uf.name,
                        uf.key,
                        uf.size,
                        uf.extension,
                        uf.mime_type,
                        uf.created_at,
                        uf.used,
                        uf.used_at,
                        'storage/' || uf.key AS relative_path
                    FROM upload_files uf
                    WHERE {where_sql}
                    ORDER BY uf.created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]

    def read_document_chunks(
        self,
        document_id: str,
        center_position: int | None = None,
        before: int = 2,
        after: int = 2,
        limit: int = 20,
    ) -> dict[str, Any]:
        before = min(max(before, 0), 10)
        after = min(max(after, 0), 10)
        limit = min(max(limit, 1), 100)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc.id::text AS document_id, doc.name AS document_name, dset.name AS dataset_name
                    FROM documents doc
                    JOIN datasets dset ON dset.id = doc.dataset_id
                    WHERE doc.id = %s::uuid AND doc.archived = false
                    """,
                    (document_id,),
                )
                document = cur.fetchone()
                if not document:
                    return {"document": None, "chunks": []}
                if center_position is None:
                    cur.execute(
                        """
                        SELECT id::text AS segment_id, position, content, word_count, tokens
                        FROM document_segments
                        WHERE document_id = %s::uuid AND enabled = true AND status = 'completed'
                        ORDER BY position ASC
                        LIMIT %s
                        """,
                        (document_id, limit),
                    )
                else:
                    start = max(center_position - before, 0)
                    end = center_position + after
                    cur.execute(
                        """
                        SELECT id::text AS segment_id, position, content, word_count, tokens
                        FROM document_segments
                        WHERE document_id = %s::uuid
                          AND enabled = true
                          AND status = 'completed'
                          AND position BETWEEN %s AND %s
                        ORDER BY position ASC
                        LIMIT %s
                        """,
                        (document_id, start, end, limit),
                    )
                chunks = [self._format_chunk(dict(row)) for row in cur.fetchall()]
        return {"document": dict(document), "chunks": chunks}

    def _expand_query_terms(self, query: str) -> list[str]:
        cleaned = (query or "").strip()
        if not cleaned:
            return []
        raw_terms = [cleaned]
        for token in self._split_query(cleaned):
            raw_terms.append(token)
            raw_terms.extend(DEFAULT_FACT_EXPANSIONS.get(token.lower(), []))
            raw_terms.extend(DEFAULT_FACT_EXPANSIONS.get(token, []))
        deduped: list[str] = []
        for term in raw_terms:
            term = term.strip()
            if len(term) < 2 or term in deduped:
                continue
            deduped.append(term)
        return deduped[:12]

    def _split_query(self, query: str) -> list[str]:
        separators = " ，。！？、；：,.!?;:\n\t()（）[]【】<>《》/\\|"
        terms: list[str] = []
        current = ""
        for char in query:
            if char in separators:
                if current:
                    terms.append(current)
                    current = ""
            else:
                current += char
        if current:
            terms.append(current)
        # Add short semantic anchors for common Chinese fact questions.
        anchors = ["创始人", "创办人", "负责人", "陈总", "陈立昌", "MMB", "瞢瞢熊"]
        for anchor in anchors:
            if anchor in query:
                terms.append(anchor)
        return terms

    def _format_segment_hit(self, row: dict[str, Any], terms: list[str]) -> dict[str, Any]:
        content = row.get("content") or ""
        matched_terms = [term for term in terms if term.lower() in content.lower()]
        score = len(matched_terms) * 10 + min(len(content), 2000) / 2000
        snippet = self._best_snippet(content, matched_terms or terms)
        return {
            "dataset_id": row["dataset_id"],
            "dataset_name": row["dataset_name"],
            "document_id": row["document_id"],
            "document_name": row["document_name"],
            "canonical_document_name": self._canonical_document_name(row["document_name"]),
            "segment_id": row["segment_id"],
            "position": row["position"],
            "snippet": snippet,
            "matched_terms": matched_terms,
            "score": round(score, 3),
            "word_count": row.get("word_count"),
            "tokens": row.get("tokens"),
            "document_updated_at": row.get("document_updated_at"),
        }

    def _format_chunk(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "segment_id": row["segment_id"],
            "position": row["position"],
            "content": self._trim(row.get("content") or "", 4000),
            "word_count": row.get("word_count"),
            "tokens": row.get("tokens"),
        }

    def _best_snippet(self, content: str, terms: list[str], radius: int = 220) -> str:
        if not content:
            return ""
        lowered = content.lower()
        indexes = [lowered.find(term.lower()) for term in terms if term and lowered.find(term.lower()) >= 0]
        if not indexes:
            return self._trim(content, radius * 2)
        index = min(indexes)
        start = max(index - radius, 0)
        end = min(index + radius, len(content))
        prefix = "..." if start else ""
        suffix = "..." if end < len(content) else ""
        return prefix + content[start:end] + suffix

    def _trim(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _dedupe_segment_hits(self, hits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        seen_documents: set[str] = set()
        deferred: list[dict[str, Any]] = []
        for hit in hits:
            canonical = hit.get("canonical_document_name") or hit.get("document_name") or hit.get("document_id")
            if canonical not in seen_documents:
                selected.append(hit)
                seen_documents.add(canonical)
            else:
                deferred.append(hit)
            if len(selected) >= limit:
                return selected
        for hit in deferred:
            selected.append(hit)
            if len(selected) >= limit:
                break
        return selected

    def _canonical_document_name(self, name: str) -> str:
        simplified = re.sub(r"^\d+\s+MMB-DIFY__.*__", "", name or "")
        return simplified.strip() or name


class FileTextReader:
    """Small safe text reader for material files under the configured Dify app root."""

    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root.resolve()

    def read_file_text(self, relative_path: str, max_chars: int = 12000) -> dict[str, Any]:
        path = self._resolve(relative_path)
        max_chars = min(max(max_chars, 1), 50000)
        extension = path.suffix.lower()
        if extension in {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".html", ".htm", ".xml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
        elif extension == ".docx":
            text = self._read_docx(path)
        else:
            return {
                "relative_path": relative_path,
                "supported": False,
                "reason": "This file type is not supported by direct text reading in v2. Use indexed segments first.",
            }
        return {
            "relative_path": relative_path,
            "supported": True,
            "extension": extension,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
        }

    def _resolve(self, relative_path: str) -> Path:
        candidate = (self.app_root / relative_path).resolve()
        if candidate != self.app_root and self.app_root not in candidate.parents:
            raise ValueError("path escapes configured app root")
        if not candidate.is_file():
            raise FileNotFoundError(relative_path)
        relative_parts = candidate.relative_to(self.app_root).parts
        lowered_parts = {part.lower() for part in relative_parts}
        if "privkeys" in lowered_parts or candidate.name.lower() in {".dify_secret_key", "id_rsa", "id_ed25519"}:
            raise ValueError("private key and secret paths are not readable")
        return candidate

    def _read_docx(self, path: Path) -> str:
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(path) as archive:
            data = archive.read("word/document.xml")
        root = ET.fromstring(data)
        texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
        return "\n".join(texts)
