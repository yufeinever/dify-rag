# MMB Business Artifact Skill

Use this skill when the user asks for Word, Excel, PowerPoint, proposal documents, tables, budgets, schedules, meeting summaries, or structured attachments.

Workflow:
1. Use `search_mmb_context` or `search_mmb_materials` when enterprise facts, source files, or visual assets are needed.
2. For beautiful, visual, image-first decks, call `create_visual_ppt` with title, outline, slide_count, and style_preset when available.
3. For Word, Excel, or ordinary PPT files, call `create_office_file` with artifact_type, title, content, and instructions.
4. If a file tool returns `not_configured`, tell the user no real file was created and offer a chat draft instead.
5. Do not use terminal as the default Office generator; use terminal only as an explicit fallback after tool failure and user acceptance.
