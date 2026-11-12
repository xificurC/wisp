---
id: 'wisp-gbwxpj'
name: 'kodama'
status: 'closed'
created: '2026-11-10T14:02:40Z'
parent: null
blocked-on: []
---

## Goal

Run a loosely coordinated swarm of short-lived `wisp` sessions from one
CLI. `kodama` is the root script and holds no LLM. Agents are small,
interchangeable wisp session templates, copied per run. Order of runs
emerges from one shared board.

## Requirements (condensed)

R1 no LLM in the root. R2 one smol run = one artifact at most, one post
at least, guard ≤ 50%. R3 an agent is a wisp session template
(`kodama agent submit`, no config file, no type schema). R4
`task submit`. R5 `task await` blocks, exits 0/1/3; `status` is
instant and `watch` follows. R6 `task steer`. R7 `task log`. R8 ledger
append-only and complete. R9 per-root `kodama-sessions/`, many roots
per PC. R10 machine-wide rate limiter. R11 self-healing: 429, timeout,
crash, guard-75 (distill, not continue), empty output, failed accept,
budget. R12 a question blocks a lane, not the task; a peer or the owner
answers; `--unattended` lets a peer answer bind. R13 order emerges.
R14 every run trace readable, one task-level aggregate. R15 kodama
never edits an artifact. R16 no hidden retry. R17 a spawn copies a
template and routes the model at spawn. Full text:
`design-options-2.md` §2.

## Design

Round 2 supersedes the five systems of round 1. One substrate, ten wake
rules. Full detail with snippets and first principles:
`design-options-2.md`.

| Strategy | Next run picked by | Done declared by |
|---|---|---|
| bulletin (default) | idle-weighted random agent | accept, else quorum + audit |
| ranked | votes on open threads | top-ranked done proposal |
| auction | best bid on an open thread | award + accept |
| bounty | best bounty over estimate | bounty spent / accept |
| relay | the last post's `next:` hint | author, then audit |
| stigmergy | decaying thread score | cold + close |
| gossip | random peer sample | K independent mentions |
| clonal | agent weights from citations | accept / quorum |
| chorus | N parallel clones on a decision | merge + accept |
| queue | oldest unclaimed thread | drain + accept |

Shared substrate: `kodama-sessions/` root; `agents/<name>/` session
templates; `board/posts/` immutable JSON posts; `tasks/<id>/{task.md,files,
artifacts,root,runs,state,locks}`; `ledger.jsonl`;
`~/.kodama/{route.json,limits/}`. A spawn copies a template, rewrites
`wisp.run.json` with the probe's model pair and the task root as
parent, and runs one wisp session. Questions are scoped posts; a guard
stop runs one unguarded distill turn. `task trace` aggregates the
ledger's sessions.

Verified 2026-11-10: a copied template keeps its persona and honors a
rewritten `wisp.run.json` model pair; the test used a closed local URL,
so no model was called.

Decisions from the owner's review (2026-11-10): D1 root is
`kodama-sessions/`; D2 no write scopes, one `(task, agent)` lock; D3
agents are templates, no config files; D4 questions are async and
lane-scoped, with unattended answering; D5 guard 75 distills; D6
aggregate traces; D7 live-probe routing; D8 emergent board, ten
strategies.

Nothing is built. The open questions are in `## Gaps`.

## Gaps

| # | Question | Options | Rec |
|---|---|---|---|
| Q1 | Is `accept` mandatory? | (a) mandatory; (b) optional, quorum + audit; (c) optional, quorum only | b |
| Q2 | Which strategy is the default? | (a) bulletin; (b) ranked; (c) queue | a |
| Q3 | Does a peer answer bind? | (a) advisory by default, peer under `--unattended`; (b) always advisory; (c) always binding | a |
| Q4 | Is the board per root or per task? | (a) one root board, tasks are threads; (b) one board per task | a |
| Q5 | Is a merged trace stored or on demand? | (a) on demand; (b) a stored `trace.log` per task | a |
