# MMB Poster Generation Skill

Use this skill when the user asks for a poster, share image, campaign image, store activity image, or visual marketing asset.

Workflow:
1. Clarify missing essentials only when they block generation: theme, audience, title, key selling points, size.
2. Call `search_materials` if brand assets or source imagery are needed.
3. Call `create_poster_job` with a concise brief.
4. Tell the user the job has started and include the returned job id/status. Do not claim the final image is ready until the job reports success.
