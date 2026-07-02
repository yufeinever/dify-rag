import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from app.catalog import MaterialCatalog
from app.config import Settings
from app.dify_metadata import DifyMetadataRepository
from app.media import MediaAccessError, MediaThumbnailService, sign_material_thumbnail_url
from app.mcp import MaterialMCPServer


class FakeMetadataRepository:
    def list_datasets(self, limit: int = 50):
        return [{"id": "dataset-1", "name": "资料库", "document_count": 2, "limit": limit}]

    def list_documents(self, dataset_id=None, query=None, limit: int = 100):
        return [
            {
                "document_id": "doc-1",
                "document_name": "融资方案.pdf",
                "dataset_id": dataset_id,
                "query": query,
                "limit": limit,
                "document_url": f"/datasets/{dataset_id}/documents/doc-1" if dataset_id else None,
                "document_link_markdown": f"[融资方案.pdf](/datasets/{dataset_id}/documents/doc-1)" if dataset_id else None,
            }
        ]

    def search_segments(self, query, dataset_id=None, document_id=None, limit: int = 10):
        return [
                {
                    "dataset_id": "dataset-1",
                    "document_id": "doc-1",
                    "document_name": "瞢瞢熊智慧鮮啤交易所融资方案 0211.pdf",
                    "position": 3,
                    "segment_position": 3,
                    "snippet": "创始人：陈立昌",
                    "matched_terms": ["创始人"],
                    "score": 10.5,
                    "document_url": "/datasets/dataset-1/documents/doc-1",
                    "document_link_markdown": "[瞢瞢熊智慧鮮啤交易所融资方案 0211.pdf](/datasets/dataset-1/documents/doc-1)",
                },
                {
                    "dataset_id": "dataset-1",
                    "document_id": "doc-2",
                    "document_name": "技术部碰头会_会议记录.docx",
                    "position": 1,
                    "segment_position": 1,
                    "snippet": "陈总 - 创始人，负责资源对接和融资",
                    "matched_terms": ["陈总", "创始人"],
                    "score": 20.2,
                    "document_url": "/datasets/dataset-1/documents/doc-2",
                    "document_link_markdown": "[技术部碰头会_会议记录.docx](/datasets/dataset-1/documents/doc-2)",
                },
            ][:limit]

    def read_document_chunks(self, document_id, center_position=None, before: int = 2, after: int = 2, limit: int = 20):
        return {
            "document": {
                "dataset_id": "dataset-1",
                "document_id": document_id,
                "document_name": "融资方案.pdf",
                "document_url": f"/datasets/dataset-1/documents/{document_id}",
                "document_link_markdown": f"[融资方案.pdf](/datasets/dataset-1/documents/{document_id})",
            },
            "chunks": [{"position": center_position or 1, "segment_position": center_position or 1, "content": "创始人：陈立昌"}],
        }

    def search_upload_files(self, query=None, extension=None, limit: int = 50):
        if query and "Logo" in query:
            return [
                {
                    "upload_file_id": "image-1",
                    "name": "MMB啤酒熊品牌Logo.png",
                    "key": "upload_files/tenant/logo.png",
                    "extension": "png",
                    "mime_type": "image/png",
                    "relative_path": "storage/upload_files/tenant/logo.png",
                    "file_kind": "image",
                    "is_renderable_image": True,
                    "thumbnail_url": "/material-agent/media/thumbnails/image-1.webp?w=1024&q=78&timestamp=1&nonce=n&sign=s",
                    "thumbnail_markdown_image": "![MMB啤酒熊品牌Logo.png](/material-agent/media/thumbnails/image-1.webp?w=1024&q=78&timestamp=1&nonce=n&sign=s)",
                    "original_preview_url": "/files/image-1/image-preview?timestamp=1&nonce=n&sign=s",
                    "original_link_markdown": "[查看原图](/files/image-1/image-preview?timestamp=1&nonce=n&sign=s)",
                    "markdown_image": "![MMB啤酒熊品牌Logo.png](/material-agent/media/thumbnails/image-1.webp?w=1024&q=78&timestamp=1&nonce=n&sign=s)",
                }
            ]
        return [
            {
                "upload_file_id": "file-1",
                "name": "瞢瞢熊智慧鮮啤交易所融资方案 0211.pdf",
                "key": "upload_files/tenant/file.pdf",
                "extension": "pdf",
                "relative_path": "storage/upload_files/tenant/file.pdf",
            }
        ]


class MaterialMCPServerTests(unittest.TestCase):
    def _server(self, tmp_path: Path) -> MaterialMCPServer:
        app_root = tmp_path / "dify-app"
        storage = app_root / "storage"
        storage.mkdir(parents=True)
        (storage / "note.txt").write_text("MMB 创始人：陈立昌", encoding="utf-8")
        (storage / "guide.md").write_text("# MMB 指南\n\n- Logo 展示", encoding="utf-8")
        catalog = MaterialCatalog(app_root, tmp_path / "catalog.sqlite", max_hash_bytes=1024 * 1024, max_scan_files=100)
        catalog.sync(["storage"])
        settings = Settings(
            MATERIAL_CATALOG_APP_ROOT=app_root,
            MATERIAL_CATALOG_ALLOWED_ROOTS="storage",
            MATERIAL_CATALOG_DB_PATH=tmp_path / "catalog.sqlite",
            MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS=60,
            DIFY_DB_PASSWORD="unused",
        )
        return MaterialMCPServer(settings, catalog, FakeMetadataRepository())

    def test_initialize_and_tool_list(self) -> None:
        with TemporaryDirectory() as tmp:
            server = self._server(Path(tmp))

            initialized = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "material-catalog-mcp")
            self.assertIn("tools", initialized["result"]["capabilities"])

            listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = [tool["name"] for tool in listed["result"]["tools"]]
            self.assertEqual(
                names,
                [
                    "server_info",
                    "list_material_roots",
                    "list_datasets",
                    "list_documents",
                    "search_segments",
                    "read_document_chunks",
                    "search_files",
                    "read_file_text",
                    "profile_materials",
                    "list_material_changes",
                ],
            )
            search_schema = next(tool for tool in listed["result"]["tools"] if tool["name"] == "search_segments")["inputSchema"]
            self.assertEqual(search_schema["required"], ["query"])
            self.assertNotIn("required_marker", search_schema["properties"]["query"])

    def test_tool_calls_return_structured_content(self) -> None:
        with TemporaryDirectory() as tmp:
            server = self._server(Path(tmp))

            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search_segments", "arguments": {"query": "MMB 的创始人是谁", "limit": 10}},
                }
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(result["structuredContent"]["count"], 2)
            self.assertIn("陈立昌", result["structuredContent"]["hits"][0]["snippet"])

            roots = server.handle(
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_material_roots", "arguments": {}}}
            )["result"]["structuredContent"]["roots"]
            self.assertNotIn("path", roots[0])
            self.assertEqual(roots[0]["relative_path"], "storage")

            info = server.handle(
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "server_info", "arguments": {}}}
            )["result"]["structuredContent"]
            self.assertTrue(info["read_only"])
            self.assertNotIn("app_root", info)

            files = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "search_files", "arguments": {"query": "融资方案"}},
                }
            )["result"]["structuredContent"]
            self.assertEqual(files["upload_files"][0]["name"], "瞢瞢熊智慧鮮啤交易所融资方案 0211.pdf")

            logo_files = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {"name": "search_files", "arguments": {"query": "Logo"}},
                }
            )["result"]["structuredContent"]
            self.assertTrue(logo_files["upload_files"][0]["is_renderable_image"])
            self.assertIn("/material-agent/media/thumbnails/image-1.webp", logo_files["upload_files"][0]["thumbnail_markdown_image"])
            self.assertIn("/files/image-1/image-preview", logo_files["upload_files"][0]["original_link_markdown"])

            markdown = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {"name": "read_file_text", "arguments": {"relative_path": "storage/guide.md"}},
                }
            )["result"]["structuredContent"]
            self.assertEqual(markdown["render_as"], "markdown")
            self.assertIn("# MMB 指南", markdown["text"])

            profile = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {"name": "profile_materials", "arguments": {"limit": 1}},
                }
            )["result"]["structuredContent"]
            self.assertNotIn("path", profile["recent_assets"][0])
            self.assertNotIn("sha256", profile["recent_assets"][0])

    def test_upload_image_preview_urls_are_signed_when_secret_is_configured(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_root = tmp_path / "dify-app"
            app_root.mkdir()
            settings = Settings(
                MATERIAL_CATALOG_APP_ROOT=app_root,
                MATERIAL_CATALOG_ALLOWED_ROOTS="storage",
                MATERIAL_CATALOG_DB_PATH=tmp_path / "catalog.sqlite",
                MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS=60,
                DIFY_DB_PASSWORD="unused",
                DIFY_FILE_PREVIEW_SECRET_KEY="test-secret",
            )
            repo = DifyMetadataRepository(settings)
            row = repo._format_upload_file(
                {
                    "upload_file_id": "image-1",
                    "name": "MMB啤酒熊品牌Logo.png",
                    "extension": "png",
                    "mime_type": "image/png",
                }
            )
            self.assertTrue(row["is_renderable_image"])
            self.assertIn("/material-agent/media/thumbnails/image-1.webp?w=1024&q=78&timestamp=", row["thumbnail_markdown_image"])
            self.assertIn("/files/image-1/image-preview?timestamp=", row["original_link_markdown"])
            self.assertIn("&nonce=", row["thumbnail_markdown_image"])
            self.assertIn("&sign=", row["thumbnail_markdown_image"])
            self.assertEqual(row["markdown_image"], row["thumbnail_markdown_image"])

    def test_document_evidence_link_fields_are_formatted(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                MATERIAL_CATALOG_APP_ROOT=tmp_path / "dify-app",
                MATERIAL_CATALOG_ALLOWED_ROOTS="storage",
                MATERIAL_CATALOG_DB_PATH=tmp_path / "catalog.sqlite",
                MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS=60,
                DIFY_DB_PASSWORD="unused",
            )
            repo = DifyMetadataRepository(settings)
            hit = repo._format_segment_hit(
                {
                    "dataset_id": "dataset-1",
                    "dataset_name": "资料库",
                    "document_id": "doc-1",
                    "document_name": "融资方案.pdf",
                    "segment_id": "segment-1",
                    "position": 7,
                    "content": "MMB 创始人：陈立昌",
                    "word_count": 10,
                    "tokens": 20,
                    "document_updated_at": None,
                },
                ["创始人"],
            )
            self.assertEqual(hit["document_url"], "/datasets/dataset-1/documents/doc-1")
            self.assertEqual(hit["document_link_markdown"], "[融资方案.pdf](/datasets/dataset-1/documents/doc-1)")
            self.assertEqual(hit["segment_position"], 7)

            chunk = repo._format_chunk({"segment_id": "segment-1", "position": 8, "content": "上下文", "word_count": 3, "tokens": 4})
            self.assertEqual(chunk["segment_position"], 8)

    def test_file_query_expands_common_chinese_visual_terms(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                MATERIAL_CATALOG_APP_ROOT=tmp_path / "dify-app",
                MATERIAL_CATALOG_ALLOWED_ROOTS="storage",
                MATERIAL_CATALOG_DB_PATH=tmp_path / "catalog.sqlite",
                MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS=60,
                DIFY_DB_PASSWORD="unused",
            )
            repo = DifyMetadataRepository(settings)
            terms = repo._split_file_query("广场啤酒夜景")
            self.assertIn("广场", terms)
            self.assertIn("夜景", terms)
            self.assertIn("鲜啤", terms)
            self.assertIn("交易所", terms)

    def test_thumbnail_service_generates_cached_webp_and_rejects_bad_access(self) -> None:
        with TemporaryDirectory() as tmp:
            from PIL import Image

            tmp_path = Path(tmp)
            app_root = tmp_path / "dify-app"
            source = app_root / "storage" / "upload_files" / "tenant" / "logo.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (1800, 900), color=(24, 96, 160)).save(source)
            settings = Settings(
                MATERIAL_CATALOG_APP_ROOT=app_root,
                MATERIAL_CATALOG_ALLOWED_ROOTS="storage",
                MATERIAL_CATALOG_DB_PATH=tmp_path / "catalog.sqlite",
                MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS=60,
                MATERIAL_CATALOG_MEDIA_CACHE_DIR=tmp_path / "media-cache",
                DIFY_DB_PASSWORD="unused",
                DIFY_FILE_PREVIEW_SECRET_KEY="test-secret",
            )

            class Lookup:
                def get_upload_file(self, upload_file_id: str):
                    if upload_file_id == "image-1":
                        return {"upload_file_id": upload_file_id, "key": "upload_files/tenant/logo.png", "extension": "png"}
                    return None

            service = MediaThumbnailService(settings, Lookup())
            thumbnail_url = sign_material_thumbnail_url(settings, "image-1")
            self.assertIsNotNone(thumbnail_url)
            parsed = urlparse(thumbnail_url or "")
            query = parse_qs(parsed.query)
            rendered = service.render_thumbnail(
                "image-1",
                int(query["w"][0]),
                int(query["q"][0]),
                query["timestamp"][0],
                query["nonce"][0],
                query["sign"][0],
            )
            self.assertTrue(rendered.is_file())
            with Image.open(rendered) as image:
                self.assertEqual(image.format, "WEBP")
                self.assertLessEqual(max(image.size), 1024)

            rendered_again = service.render_thumbnail(
                "image-1",
                int(query["w"][0]),
                int(query["q"][0]),
                query["timestamp"][0],
                query["nonce"][0],
                query["sign"][0],
            )
            self.assertEqual(rendered, rendered_again)

            with self.assertRaises(MediaAccessError):
                service.render_thumbnail("image-1", 1024, 78, None, None, None)

            missing_url = sign_material_thumbnail_url(settings, "missing")
            missing_query = parse_qs(urlparse(missing_url or "").query)
            with self.assertRaises(MediaAccessError) as error:
                service.render_thumbnail(
                    "missing",
                    int(missing_query["w"][0]),
                    int(missing_query["q"][0]),
                    missing_query["timestamp"][0],
                    missing_query["nonce"][0],
                    missing_query["sign"][0],
                )
            self.assertEqual(error.exception.status_code, 404)

    def test_tool_error_is_mcp_tool_error_not_jsonrpc_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            server = self._server(Path(tmp))

            response = server.handle(
                {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "delete_file", "arguments": {}}}
            )
            self.assertTrue(response["result"]["isError"])
            self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "UNKNOWN_TOOL")


if __name__ == "__main__":
    unittest.main()
