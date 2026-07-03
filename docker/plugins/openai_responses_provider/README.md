# MMB OpenAI Responses Provider

Private Dify model provider forked from the official `langgenius/openai` plugin.

It defaults to the OpenAI Responses API and can append OpenAI native hosted tools while preserving Dify function/MCP tools:

- `web_search`, enabled by default
- `code_interpreter`, disabled by default
- `file_search`, disabled by default and only enabled when OpenAI vector store ids are configured

This plugin is intentionally separate from the official OpenAI plugin and from `langgenius/openai_api_compatible`.
