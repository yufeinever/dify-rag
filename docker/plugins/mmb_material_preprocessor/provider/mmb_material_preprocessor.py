import requests
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class MmbMaterialPreprocessorProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        base_url = (credentials.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ToolProviderCredentialValidationError("Please input MinerU base_url")
        try:
            response = requests.get(f"{base_url}/docs", timeout=10)
        except Exception as exc:
            raise ToolProviderCredentialValidationError(f"Cannot connect to MinerU: {exc}") from exc
        if response.status_code >= 500:
            raise ToolProviderCredentialValidationError(f"MinerU returned HTTP {response.status_code}")
