# Next
- Ask the user to pick (a), (b), or (c) from the ticket `## Gaps`; build nothing before that answer.

# Open
- None. The port decision is a STOP question and lives in ticket `## Gaps`.

# Cache
- A wispy session jsonl line is one typed record: `system`, `user`, `assistant`, `tool`. Assistant records carry `output` as a list of reasoning, text and tool_call blocks, plus `usage` as a list of chunks; tool records carry `content` and `exit`. Reading per-round sizes for port 2 means walking those records, not parsing `wisp.usage`. (From: wisp-sessions/wisp-5rva5v-001/wisp.jsonl, wisp lines 3527-3620) (Serves: cold)
- BC's four load-bearing rule texts are exported constants in `kernel/src/compression-rules.ts`; `kernel/src/nudge-text.ts` renders the nudge and embeds them; `kernel/DESIGN-prompts.md` documents the override layers, where rule text is risk-gated and surface text is free. Port 1 copies text from the first file and needs nothing from the other two. (From: kernel/src/compression-rules.ts, kernel/src/nudge-text.ts, kernel/DESIGN-prompts.md) (Serves: cold)

# Pointers
- BC repo: /home/pnagyux/code/billion-context (branch master, read only, no edits made)
- Ticket: /home/pnagyux/code/wisp/.tickets/wisp-q1d046/ticket.md
- Session: /home/pnagyux/code/wisp/wisp-sessions/wisp-q1d046-001
- Port targets: /home/pnagyux/code/wisp/wispy/prompts/distill-rules.md, /home/pnagyux/code/wisp/wispy/wispy, /home/pnagyux/code/wisp/wisp/wisp
- Doctrine source: /home/pnagyux/code/billion-context/kernel/src/compression-rules.ts
