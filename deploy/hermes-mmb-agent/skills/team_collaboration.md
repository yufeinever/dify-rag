# MMB Team Collaboration Skill

Use this skill in team or group contexts when the user wants to save, share, archive, or continue a team work product.

Workflow:
1. Treat group conversation as team context and private chat as personal context.
2. Do not save personal drafts to a team space without explicit confirmation.
3. When the user confirms saving, call `save_team_asset` with the title, content, visibility, and source request id if available.
4. Summarize what was saved and how the team can continue from it.
