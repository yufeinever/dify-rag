# MMB Material Exploration Skill

Use this skill when the user asks to find images, source files, historical material, campaign references, product files, logos, founder/team photos, or visual assets.

Workflow:
1. Call `search_mmb_materials` with concrete keywords and optional extension filters.
2. If the user needs factual content rather than files, use `search_mmb_context` instead.
3. Return a short list of the most useful assets, why they fit, and any missing constraints.
4. If the user wants to use an asset in a poster, PPT, or document, pass the relevant asset information into the next workflow tool.
