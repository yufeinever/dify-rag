from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import Settings


class DifyMetadataRepository:
    """Read-only access to Dify metadata needed by the material catalog agent."""

    settings: Settings

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _connect(self) -> psycopg.Connection[Any]:
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
