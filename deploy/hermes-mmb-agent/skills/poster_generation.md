# MMB Poster Generation Skill

Use this skill when the user asks for a poster, share image, campaign image, store activity image, or visual marketing asset.

Workflow:
1. Clarify missing essentials only when they block generation: theme, audience, title, key selling points, size.
2. Call `search_mmb_materials` if brand assets, source imagery, or campaign references are needed.
3. Call `create_poster` with a concise brief. Do not call old `create_poster_job` unless operating against a legacy server.
4. Tell the user the job has started, include the estimated time, and include the returned job id only as a tracking id.
5. If the current channel supports background delivery, tell the user the finished image will be sent back automatically; do not ask the user to manually paste the job id into Dify.

Constraints:
- Do not claim the final image is ready until the job status is `succeeded` and a `poster_url` is available.
- Channel-specific image upload and message delivery belong to the delivery layer, not the poster generator.
