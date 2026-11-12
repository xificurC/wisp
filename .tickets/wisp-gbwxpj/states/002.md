# Next
- Ask the owner for answers to ticket `## Gaps` Q1-Q5. Q1 (accept rule), Q2 (default strategy), and Q4 (board scope) block the first slice; Q3 and Q5 can take the documented defaults.
- On each answer, edit the ticket body and drop the answered row from `## Gaps`.
- After the answers, build the substrate first: `agent submit`, `task submit`, spawn copy, board helpers, locks, ledger, router, limiter; then the digest and the bulletin scheduler.

# Open
- None. STOP distill: the five questions live in ticket `## Gaps`.

# Cache
- A copied wisp session template keeps its persona and honors a rewritten `wisp.run.json` model; tested 2026-11-10 with a closed local URL, so no model call. This is the mechanism behind R17. (From: `wisp/wisp` `write_run_setup`/`load_run_setup`, the copy test) (Serves: Next)
- `WISP_SESSIONS_ROOT` is the session root (expanduser only), so `kodama` can place templates under `kodama-sessions/agents/` and run copies under `kodama-sessions/tasks/<id>/runs/`; `wisp new -s` writes the persona as the first `wisp.jsonl` system record, and `wisp run` appends a user record to it. (From: `wisp/wisp` `sessions_root`, `write_initial_log`, `run_agent_loop`) (Serves: Next)
- `wisp continue` fails on a system-only or finished-assistant tail; it runs only when the tail is `user` or `tool`. This is why a guard stop distills instead of continuing. (From: `wisp/wisp` `continue_agent_loop`) (Serves: Next)
- `wisp.log` records `http_error ... err=429`; `wisp.usage` holds in/out/cost/context; exit 75 is the guard; SIGTERM commits the tail. kodama's recovery reads these, not the transcript. (From: `wisp/wisp` `sse_stream`, `usage_line`, `run_prepared`) (Serves: Next)
- The live model route is the zsh `__wisp_load_probe` / `__wisp_route`: `/monitor/api/status` + `/monitor/api/v1/load`, deepseek-v4.1-flash xhigh when every endpoint is online and no endpoint waits, else glm-5.3 high. (From: `~/share/dotfiles/zsh/.funcs`) (Serves: Next)
- `wisp render-past` is read-only and prints to stdout; `wisp ls --tree` uses the parent's children list, which is last-writer-wins. The ledger must index run paths; `task trace` must not trust the tree. (From: `wisp/wisp` `render_past`, `link_child`, `tree_sessions`) (Serves: Next)
- Prior art `wispies` is one plan file plus an actuator with types, chems, write scopes, and ladders; kodama drops all four and keeps the board. (From: `.tickets/ai-wpueub/design-options.md`) (Serves: cold)

# Pointers
- Design doc: `.tickets/wisp-gbwxpj/design-options-2.md` (927 lines; §3 substrate, §4 wake, §5 questions, §6 done, §7 recovery, §8 traces, §9 ten strategies, §10 defaults, §11 questions).
- Round 1: `.tickets/wisp-gbwxpj/design-options.md` (superseded).
- Ticket: `.tickets/wisp-gbwxpj/ticket.md` (83 lines).
- wisp CLI: `./wisp/wisp --help`.
- Router source: `~/share/dotfiles/zsh/.funcs` (`__wisp_load_probe`, `__wisp_route`).
- No kodama code exists; the first slice creates `kodama/kodama`.
- Branch: `main`. Session dir: `/home/pnagyux/code/wisp/wisp-sessions/wisp-gbwxpj-002`.
