# MMB Brand QA Skill

Use this skill when the user asks about MMB brand, product, policy, official phrasing, customer cases, training material, financing material, or internal facts.

Workflow:
1. Call `search_mmb_context` with the user's factual question.
2. If the result is thin or ambiguous, ask a short clarification or call `search_mmb_context` again with a narrower query/document constraint.
3. Answer with clear source-aware wording. Do not invent prices, promises, or claims that are not supported by retrieved material.
4. If the question needs business judgment beyond retrieval, call `answer_mmb_question`; if it returns `not_configured`, answer directly with GPT-5.5 using the retrieved evidence.
5. If the question is about public external facts, use web search first, then combine with enterprise knowledge when relevant.
