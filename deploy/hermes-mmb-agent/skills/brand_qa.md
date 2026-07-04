# MMB Brand QA Skill

Use this skill when the user asks about MMB brand, product, policy, official phrasing, customer cases, training material, or internal facts.

Workflow:
1. Call `search_knowledge` with the user's factual question.
2. If the result is thin or ambiguous, ask a short clarification or call `read_knowledge` for the most relevant document.
3. Answer with clear source-aware wording. Do not invent prices, promises, or claims that are not supported by retrieved material.
4. If the question is about public external facts, use web search first, then combine with enterprise knowledge when relevant.
