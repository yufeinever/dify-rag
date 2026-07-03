import ast
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class OpenAIResponsesProviderStaticTests(unittest.TestCase):
    def test_manifest_declares_private_plugin(self):
        manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())
        self.assertEqual(manifest["author"], "mmb")
        self.assertEqual(manifest["name"], "openai_responses_provider")
        self.assertEqual(manifest["plugins"]["models"], ["provider/openai_responses_provider.yaml"])

    def test_provider_schema_is_separate_from_official_openai(self):
        provider = yaml.safe_load((ROOT / "provider" / "openai_responses_provider.yaml").read_text())
        self.assertEqual(provider["provider"], "openai_responses_provider")
        self.assertEqual(provider["label"]["en_US"], "MMB OpenAI Responses")
        self.assertEqual(
            provider["extra"]["python"]["provider_source"],
            "provider/openai_responses_provider.py",
        )

    def test_hosted_tool_fields_exist_for_model_and_provider_credentials(self):
        provider = yaml.safe_load((ROOT / "provider" / "openai_responses_provider.yaml").read_text())
        model_vars = {
            item["variable"]
            for item in provider["model_credential_schema"]["credential_form_schemas"]
        }
        provider_vars = {
            item["variable"]
            for item in provider["provider_credential_schema"]["credential_form_schemas"]
        }
        expected = {
            "enable_web_search",
            "enable_code_interpreter",
            "enable_file_search",
            "openai_vector_store_ids",
        }
        self.assertTrue(expected.issubset(model_vars))
        self.assertTrue(expected.issubset(provider_vars))

    def test_llm_injects_openai_hosted_tools_only_on_responses_protocol(self):
        source = (ROOT / "models" / "llm" / "llm.py").read_text()
        ast.parse(source)
        self.assertIn('credentials.get("api_protocol", "responses") == "responses"', source)
        self.assertIn('{"type": "web_search"}', source)
        self.assertIn('"type": "code_interpreter", "container": {"type": "auto"}', source)
        self.assertIn('"type": "file_search", "vector_store_ids": vector_store_ids', source)
        self.assertIn('"type": "function"', source)

    def test_base_url_accepts_root_or_v1_endpoint(self):
        source = (ROOT / "models" / "common_openai.py").read_text()
        ast.parse(source)
        self.assertIn('openai_api_base.endswith("/v1")', source)
        self.assertIn('else openai_api_base + "/v1"', source)


if __name__ == "__main__":
    unittest.main()
