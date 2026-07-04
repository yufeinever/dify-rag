from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import main


def p2p_context() -> dict[str, object]:
    return {
        "tenant_id": "tenant-a",
        "bot_id": "bot-a",
        "chat_type": "p2p",
        "open_id": "ou_a",
    }


class CapabilityApiTest(unittest.TestCase):
    def setUp(self) -> None:
        main.settings.auth_token = None
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.settings.auth_token = None

    def test_health_and_tools(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

        response = self.client.get("/v1/tools")

        self.assertEqual(response.status_code, 200)
        names = {tool["name"] for tool in response.json()["tools"]}
        self.assertIn("search_enterprise_knowledge", names)
        self.assertIn("create_poster_job", names)

    def test_auth_when_configured(self) -> None:
        main.settings.auth_token = "secret"

        self.assertEqual(self.client.get("/v1/tools").status_code, 401)
        response = self.client.get("/v1/tools", headers={"Authorization": "Bearer secret"})

        self.assertEqual(response.status_code, 200)

    def test_session_key_endpoint(self) -> None:
        response = self.client.post(
            "/v1/session-key",
            json={
                "tenant_id": "tenant-a",
                "bot_id": "bot-a",
                "chat_type": "group",
                "chat_id": "oc_1",
                "sender_open_id": "ou_a",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_key"], "tenant-a:bot-a:feishu:group:oc_1")
        self.assertTrue(data["shared_context"])

    def test_search_knowledge_wraps_sources_and_audit(self) -> None:
        original = main.clients.search_enterprise_knowledge

        async def fake_search(request):
            return {"query": request.query, "hits": [{"document_id": "doc-1", "content": "MMB"}]}

        main.clients.search_enterprise_knowledge = fake_search
        try:
            response = self.client.post(
                "/v1/knowledge/search",
                json={"context": p2p_context(), "query": "MMB 是什么", "limit": 3},
            )
        finally:
            main.clients.search_enterprise_knowledge = original

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "search_enterprise_knowledge")
        self.assertEqual(data["sources"][0]["document_id"], "doc-1")

    def test_create_team_artifact(self) -> None:
        response = self.client.post(
            "/v1/artifacts/team",
            json={
                "context": {
                    "tenant_id": "tenant-a",
                    "bot_id": "bot-a",
                    "chat_type": "group",
                    "chat_id": "oc_1",
                    "sender_open_id": "ou_a",
                },
                "artifact_type": "copywriting",
                "title": "活动文案",
                "content": "这是一版团队确认过的文案。",
                "visibility": "team",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tool"], "create_team_artifact")
        self.assertEqual(data["data"]["visibility"], "team")

    def test_mcp_initialize_and_tools_list(self) -> None:
        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["serverInfo"]["name"], "mmb-capability-center")

        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

        self.assertEqual(response.status_code, 200)
        names = {tool["name"] for tool in response.json()["result"]["tools"]}
        self.assertIn("search_knowledge", names)
        self.assertIn("create_artifact", names)
        self.assertIn("save_team_asset", names)

    def test_mcp_search_knowledge_call(self) -> None:
        original = main.clients.search_enterprise_knowledge

        async def fake_search(request):
            self.assertEqual(request.context.channel, "hermes")
            self.assertEqual(request.query, "MMB 品牌")
            return {"query": request.query, "hits": [{"document_id": "doc-1"}]}

        main.clients.search_enterprise_knowledge = fake_search
        try:
            response = self.client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search_knowledge", "arguments": {"query": "MMB 品牌", "user_id": "u1"}},
                },
            )
        finally:
            main.clients.search_enterprise_knowledge = original

        self.assertEqual(response.status_code, 200)
        data = response.json()["result"]["structuredContent"]
        self.assertTrue(data["ok"])
        self.assertEqual(data["tool"], "search_knowledge")

    def test_mcp_save_team_asset(self) -> None:
        response = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "save_team_asset",
                    "arguments": {
                        "chat_type": "group",
                        "chat_id": "oc_1",
                        "sender_open_id": "ou_a",
                        "title": "团队文案",
                        "content": "确认保存的团队产物。",
                        "visibility": "team",
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["result"]["structuredContent"]
        self.assertTrue(data["ok"])
        self.assertEqual(data["tool"], "save_team_asset")


if __name__ == "__main__":
    unittest.main()
