# MMB Material Exploration Skill

Use this skill when the user asks to find images, source files, historical material, campaign references, product files, or visual assets.

Workflow:
1. Call `search_materials` with concrete keywords and optional extension filters.
2. For text-based source files, call `read_material` before summarizing.
3. Return a short list of the most useful assets, why they fit, and any missing constraints.
4. If the user wants to use an asset in a poster or document, pass the relevant asset information into the next tool call.
