# Next
- Ask the user to close Q1–Q10 in `ticket.md` `## Gaps`. Q1 (board location) and Q3 (write-conflict policy) block the layout; take those two first.
- Build slice 1 after the answers: plan loader, inbox scan, one `implement` type, `nono` grants, result harvest, ledger, wall clock, salvage session. Order: `design-options.md` §10.
- Do not write code before Q1 and Q3 are answered.

# Open

# Cache
- `nono` (v0.80.0) is enforced on this host: Landlock V6 denies read and write on any unlisted path; non-interactive mode exits without `--allow-cwd` (which auto-includes the cwd read-only); the default profile already grants write on `/tmp` and read on `/usr`, `/etc/ssl`, and the resolver files; a grant on a non-existent path does nothing and does not warn. (From: `nono wrap --help`, four live probes under `/tmp`) (Serves: Next)
- A bare `wisp new -m MODEL` writes `wisp.jsonl` and `wisp.run.json`, so a never-run session is a valid `--parent`; `link_child` appends to the parent's `children` with last-writer-wins, so concurrent task sessions can lose a link and the board must use its own `parent` field. (From: `wisp/wisp` `new_session`, `link_child`) (Serves: Next)
- `WISP_SESSIONS_ROOT` sets a flat session root, one dir per `--name`; `wisp run` has no wall clock limit and no model retry; `--context-guard` stops at a round boundary with exit 75 and keeps the session resumable. The actuator must own the timer and the retry. (From: `wisp run --help`, `wisp/wisp` `sessions_root`) (Serves: Next)
- LiteLLM gives no per-model in-flight gauge. `/health` is ~6 kB (quota), `/metrics/` is ~12.8 MB (global in-flight, per-deployment rpm, TTFT, queue), `/v1/model/info` is ~254 kB (price, context, tools). Derive the rate from two counter samples; sample every 15 s. (From: rev 1 probe record in `design-options.md` §7.3) (Serves: cold)
- Ticket and its two sessions moved from `/home/pnagyux/code/gti/ai` to `/home/pnagyux/code/wisp` on 2026-11-09; the `SESSION DIR` text inside each `wisp.jsonl` still names the old path and stays historical. (From: `mv` of `.tickets/ai-wpueub`, `wisp-sessions/ai-wpueub-001`, `wisp-sessions/ai-wpueub-002`) (Serves: cold)

# Pointers
- Ticket: `/home/pnagyux/code/wisp/.tickets/ai-wpueub/ticket.md`
- Design: `/home/pnagyux/code/wisp/.tickets/ai-wpueub/design-options.md` (rev 2), `design-options-v1.md`
- Wisp source: `/home/pnagyux/code/wisp/wisp/wisp`
- Wispy source: `/home/pnagyux/code/gti/ai/wispy/wispy`
- This design run: `/home/pnagyux/code/wisp/wisp-sessions/ai-wpueub-002`; earlier run: `.../ai-wpueub-001`
- Company LiteLLM server probes: `/health`, `/v1/model/info`, `/metrics/`
