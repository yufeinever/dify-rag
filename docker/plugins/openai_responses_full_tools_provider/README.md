# MMB OpenAI Responses Full Tools Provider

Private Dify model provider forked from the official `langgenius/openai` plugin.

It defaults to the OpenAI Responses API and can append OpenAI native hosted tools while preserving Dify function/MCP tools:

- `web_search`, enabled by default
- `code_interpreter`, enabled by default
- `file_search`, enabled by default and added when OpenAI vector store ids are configured
- remote MCP `mmb_materials`, disabled by default and enabled by configuring the public material MCP URL plus bearer token
- Dify document attachments, forwarded to Responses `input_file` by URL or base64 data
- Per-app hosted-tool profiles, including `web_and_code` for direct model generation without File Search or material MCP
- Optional Code Interpreter PPTX publishing through the authenticated Dify artifact relay

This plugin is intentionally separate from the official OpenAI plugin and from `langgenius/openai_api_compatible`.
