import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.catalog import MaterialCatalog
from app.config import Settings
from app.mcp import MaterialMCPServer


class FakeMetadataRepository:
    def list_datasets(self, limit: int = 50):
        return [{"id": "dataset-1", "name": "资料库", "document_count": 2, "limit": limit}]

    def list_documents(self, dataset_id=None, query=None, limit: int = 100):
        return [{"document_id": "doc-1", "document_name": "融资方案.pdf", "dataset_id": dataset_id, "query": query, "limit": limit}]

    def search_segments(self, query, dataset_id=None, document_id=None, limit: int = 10):
        return [
            {
                "document_id": "doc-1",
                "document_name": "瞢瞢熊智慧鮮啤交易所融资方案 0211.pdf",
                "position": 3,
                "snippet": "创始人：陈立昌",
                "matched_terms": ["创始人"],
                "score": 10.5,
            },
            {
                "document_id": "doc-2",
                "document_name": "技术部碰头会_会议记录.docx",
                "position": 1,
                "snippet": "陈总 - 创始人，负责资源对接和融资",
                "matched_terms": ["陈总", "创始人"],
                "score": 20.2,
            },
        ][:limit]

    def read_document_chunks(self, document_id, center_position=None, before: int = 2, after: int = 2, limit: int = 20):
        return {
            "document": {"document_id": document_id, "document_name": "融资方案.pdf"},
            "chunks": [{"position": center_position or 1, "content": "创始人：陈立昌"}],
        }

    def search_upload_files(self, query=None, extension=None, limit: int = 50):
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

            profile = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {"name": "profile_materials", "arguments": {"limit": 1}},
                }
            )["result"]["structuredContent"]
            self.assertNotIn("path", profile["recent_assets"][0])
            self.assertNotIn("sha256", profile["recent_assets"][0])

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
