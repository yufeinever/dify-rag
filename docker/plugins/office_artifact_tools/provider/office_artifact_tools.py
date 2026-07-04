from dify_plugin import ToolProvider


class OfficeArtifactToolsProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        return None
