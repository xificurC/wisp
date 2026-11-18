<git-commit-rules>
Never leak the used LLM. This includes the API key, the URL, the model alias. Use broader terms like "company LiteLLM server", and generic model names like "DeepSeek V4.1 Flash".

A local, uncommitted `pre-commit` hook scans the staged lines for the company name, the endpoint host, API keys, and API model ids. The hook may refuse the commit and prints one fix hint per rule. Fix the text, re-stage, and commit again. Never pass `--no-verify`.
</git-commit-rules>

<final-assistant-reply>

Rules for your final answer:

- factual. No fluff.
- context-free: the final answer stands on its own (the user need not read the entire turn).
- state the goal of this turn first.
- start with a TLDR 1 or 2 sentence explanation of this turn.
- if a claim needs context, provide it. If you use a novel name or phrase, define it.
- for all prose: one name per thing, repeated; no "this", "it" or "that" unless its noun is in the same sentence; active voice; under 25 words a sentence; no preamble, no recap, no closer.
- present facts causally. You have 2 choices, either start from the facts and work backward to the "axioms", or start from the axioms and work forward to the facts.

</final-assistant-reply>
