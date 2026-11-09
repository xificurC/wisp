# Next
- Ask the user to choose the drafting gate model from the ticket `## Gaps`.
- Start the review half after the user's go-ahead: write `.agents/skills/goldfish-review/SKILL.md` and one skill per reviewer, plus `docs/standards/`.
- Keep the review half independent of the gate choice; only the drafting half waits.

# Open
- None. The gate question is recorded in the ticket `## Gaps`.

# Cache
- EGM corpus is 20,875 words: 7 skills, 10 personas, 5 rubrics; `egm-review` is 3,140 words. (From: wc -w over `skills/*/SKILL.md`, `agents/*.md`, `resources/document_standards/*.md`) (Serves: Next)
- wispy distills and clears `.phase` after every finished work run; wispy has no awaiting-approval state. (From: `wispy/wispy` `drive()` and `decide_after_work()`, `md/design/wispy.md`) (Serves: Next)
- Child recipe: `wisp new --parent -s <(wisp build-system-prompt --wisp --skills --agents-md < <(wisp skill read NAME))`, then `wisp run -d "$CHILD"`, then `wisp response -d "$CHILD"`. (From: wisp system prompt subagent laws, `wisp --help`) (Serves: Next)
- `wisp new -s` fixes the whole system prompt, so a Goldfish child sees no host instruction files; this is stronger isolation than EGM's host harnesses. (From: `md/design/session-model.md`, `md/design/skills.md`, EGM `docs/harnesses.md`) (Serves: Next)
- A wisp child always has bash and python3, so Goldfish read-only is instruction only; EGM's Claude adapters set read-only tools. (From: `wisp --help` tool list, EGM `agents/*.md`, `docs/harnesses.md`) (Serves: Next)
- Port order: review half first (maps 1:1 onto wisp), draft half second (needs the gate decision), skip bootstrap and drift at first. (From: ticket Recommendation, EGM `docs/getting_started.md`) (Serves: Next)

# Pointers
- Ticket: `/home/pnagyux/code/wisp/.tickets/wisp-4bojxp/ticket.md`
- EGM repo: `/home/pnagyux/code/elephant-goldfish-model`
- wisp repo: `/home/pnagyux/code/wisp`
- wisp daemon-less commands: `wisp skill ls`, `wisp skill read NAME`, `wisp build-system-prompt --wisp --skills --agents-md`, `wisp usage -d DIR`, `wisp ls --tree`
- wispy commands: `wispy run --skills LIST`, `wispy continue`, `wispy steer`, `wispy response`
- Session dir: `/home/pnagyux/code/wisp/wisp-sessions/wisp-4bojxp-001`
