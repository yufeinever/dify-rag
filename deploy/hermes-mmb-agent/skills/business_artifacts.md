# MMB Business Artifact Skill

Use this skill when the user asks for Word, Excel, PowerPoint, proposal documents, tables, budgets, schedules, meeting summaries, or structured attachments.

Workflow:
1. Build the content yourself with GPT-5.5, using `search_knowledge` or `search_materials` when enterprise facts or source files are needed.
2. Call `create_artifact` only when a real file or persistent artifact is required.
3. For Excel, provide structured sheets and columns in the content.
4. For PPT, provide slide titles and bullet points.
5. For Word, provide a clean Markdown-like document structure.
