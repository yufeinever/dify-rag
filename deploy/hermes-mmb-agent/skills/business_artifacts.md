# MMB Business Artifact Skill

Use this skill when the user asks for Word, Excel, PowerPoint, proposal documents, tables, budgets, schedules, meeting summaries, or structured attachments. PPT, slides, decks, presentations, and roadshows are always handled by `create_visual_ppt`; `create_office_file` is Word/Excel only.

Workflow:
1. Use `search_mmb_context` or `search_mmb_materials` when enterprise facts, source files, or visual assets are needed.
2. For any PPT/deck/presentation request, call `create_visual_ppt` with title, outline, slide_count, and style_preset when available.
3. For Word or Excel files, call `create_office_file` with artifact_type, title, content, and instructions. Do not send PPT requests to `create_office_file`.
4. If a file tool returns `delivery_registered=true`, stop the workflow and tell the user the real file will be sent back automatically.
5. If a file tool returns `not_configured` or `blocked_missing_file`, tell the user no real file was created and offer a chat draft instead.
6. Do not use terminal as the default Office generator; use terminal only as an explicit fallback after tool failure and explicit user acceptance.
