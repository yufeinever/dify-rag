from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile

from models.llm.pptx_artifacts import (
    PptxArtifactError,
    collect_pptx_citations,
    publish_generated_pptx,
    render_pptx_downloads,
    validate_pptx_bytes,
)
from models.llm.llm import OpenAILargeLanguageModel


def _pptx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("ppt/presentation.xml", "<p:presentation />")
        archive.writestr("ppt/slides/slide1.xml", "<p:sld />")
    return output.getvalue()


def _response_with_citations():
    annotation = SimpleNamespace(
        type="container_file_citation",
        container_id="container_1",
        file_id="file_1",
        filename="演示文稿.pptx",
    )
    content = SimpleNamespace(annotations=[annotation, annotation])
    return SimpleNamespace(output=[SimpleNamespace(content=[content])])


class PptxArtifactTests(unittest.TestCase):
    def test_web_and_code_profile_excludes_file_search_and_material_mcp(self):
        model = object.__new__(OpenAILargeLanguageModel)
        credentials = {
            "api_protocol": "responses",
            "enable_file_search": "enabled",
            "openai_vector_store_ids": "vs_private",
            "enable_material_mcp": "enabled",
            "material_mcp_server_url": "https://example.test/mcp",
            "material_mcp_auth_token": "secret",
        }

        tools = model._build_responses_api_tools(None, credentials, "web_and_code")

        self.assertEqual(
            tools,
            [
                {"type": "web_search"},
                {"type": "code_interpreter", "container": {"type": "auto"}},
            ],
        )

    def test_collects_and_deduplicates_pptx_citations(self):
        citations = collect_pptx_citations(_response_with_citations().output)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["filename"], "演示文稿.pptx")

    def test_validates_pptx_package(self):
        validate_pptx_bytes("deck.pptx", _pptx_bytes())
        with self.assertRaises(PptxArtifactError):
            validate_pptx_bytes("deck.pptx", b"not-a-pptx")

    @patch("models.llm.pptx_artifacts.httpx.post")
    def test_downloads_uploads_and_renders_generated_pptx(self, post):
        binary_response = MagicMock()
        binary_response.read.return_value = _pptx_bytes()
        client = MagicMock()
        client.containers.files.content.retrieve.return_value = binary_response
        post.return_value.status_code = 201
        post.return_value.json.return_value = {
            "filename": "演示文稿.pptx",
            "download_url": "https://example.test/deck.pptx",
        }
        credentials = {
            "pptx_artifact_upload_url": "http://api:5001/inner/api/model-artifacts/pptx",
            "pptx_artifact_api_key": "secret",
            "pptx_artifact_tenant_id": "tenant",
            "pptx_artifact_user_id": "user",
        }

        published = publish_generated_pptx(
            client, _response_with_citations(), credentials
        )

        self.assertIn("演示文稿.pptx", render_pptx_downloads(published))
        client.containers.files.content.retrieve.assert_called_once_with(
            "file_1", container_id="container_1"
        )
        self.assertEqual(
            post.call_args.kwargs["data"], {"tenant_id": "tenant", "user_id": "user"}
        )

    def test_fails_when_model_returns_no_pptx(self):
        with self.assertRaisesRegex(PptxArtifactError, "did not return"):
            publish_generated_pptx(
                MagicMock(),
                SimpleNamespace(output=[]),
                {
                    "pptx_artifact_upload_url": "http://api",
                    "pptx_artifact_api_key": "secret",
                    "pptx_artifact_tenant_id": "tenant",
                    "pptx_artifact_user_id": "user",
                },
            )


if __name__ == "__main__":
    unittest.main()
