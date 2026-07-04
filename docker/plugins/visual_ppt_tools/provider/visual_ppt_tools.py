import os

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class VisualPptToolsProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        api_key = credentials.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ToolProviderCredentialValidationError("Please set openai_api_key or OPENAI_API_KEY")
        image_model = credentials.get("openai_image_model") or os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-2"
        if not str(image_model).strip():
            raise ToolProviderCredentialValidationError("Please set openai_image_model")
