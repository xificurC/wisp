---
id: 'ai-wpueub'
name: 'wispies'
status: 'closed'
created: '2026-10-30T15:45:13Z'
parent: null
blocked-on: []
---

## Problem

Design a swarm of agents that runs on `wisp` and takes the session,
ticket, and skill model from `wispy`.

Goals: parallel; typed agents (worker, verifier, designer); emergent
(no single top-level orchestrator); designers know how to split work;
evolutionary (at least 3 candidates, the best kept by verifiers);
optimized model and thinking by work class and current load.

Constraints: tasks are small and fast; agents are ephemeral;
information exchange is through the filesystem; top-level knobs exist
for concurrency and context guard.

## Design

Full detail: `design-options.md` (rev 2). Rev 1 is at
`design-options-v1.md`. Build order: `design-options.md` §10.

### Decided

| Question | Decision |
|---|---|
| Substrate | B. A `.swarm/` file-per-task board. `wispies` calls `wisp` directly. Wispy is not used. |
| Isolation | No git worktrees. Write scopes, feature flags, parameter grids, and scope snapshots. |
| Activation | One plan file and one actuator. No seed. The plan holds the goal, the deliverable, the types, and the root tasks. |
| Orchestrator | One `wispies` process per plan. It holds the queue and the slots. It holds no plan of its own. |
| Typing | A type is a capability set plus a model ladder. `nono` grants only the declared paths. |
| Lifecycle | One wisp session per task. A hard wall clock. One salvage session that must enqueue and finish. The task never re-enters the queue. |
| Waiting | Pheromones (chems). A task binds on named chems and emits named chems. An agent never waits. |
| Evolution | Parameter grid first, flag-gated strategies second, serialized attempts third. A bench task measures, a select task decides. |
| Router | A per-type ladder of `[model, thinking]` rungs, keyed by work class. First non-busy rung wins, else the least loaded. |
| Board writers | The actuator is the only writer of `work/`, `chems/`, `ledger/`, and `report/`. Agents write only to `inbox/`. |
| Claim protocol | Deleted. No claim, no lease, no heartbeat, no gc, no events. See `design-options.md` §6. |

### Shape

```
wispies run .swarm/plans/p-0001.toml
  scan inbox/ -> dispatch ready tasks -> reap -> flip chems -> ledger
  board empty -> unblock a stuck chem, else goal check, else next round
```

## Findings that shape the design

1. `wisp new` fixes model and system prompt. Routing is a
   session-creation decision. One session = one work class.
2. Wisp has no temperature. Diversity comes from parameter values,
   flag-gated strategy files, and different models.
3. Wisp has no API retry and no wall clock limit. The actuator owns
   both: a fresh task id, a `wisp continue`, or a kill on its own child
   process. A heartbeat is not needed; see `design-options.md` §6.1.
4. A completed round commits to `wisp.jsonl`. The mtime was a useful
   free signal in rev 1. Rev 2 has one reader, so it is unused.
5. Wispy runs a distill per work session. Too heavy for a 5-minute
   task. Wispies harvests the final message instead.
6. `WISP_SESSIONS_ROOT=.swarm/runs` gives one flat dir per session,
   named by task id. `wisp new` without `-s` still writes `wisp.jsonl`
   and `wisp.run.json`, so a never-run board session is a valid
   `--parent`. `wisp new --parent` appends to `children` with
   last-writer-wins, so the board must not depend on that list.
7. `nono wrap` is the whole rights model, and it is enforced on this
   host (nono v0.80.0, Landlock V6). An unlisted path is denied for
   read and for write. Three consequences: non-interactive mode fails
   without `--allow-cwd` (which adds the cwd read-only); the default
   profile grants write on `/tmp`, so the board must not live there;
   a grant on a non-existent path is a silent no-op.
8. A read-only agent still delivers. Its final message is the result,
   and the actuator harvests it. Only an `implement` type needs repo
   write access, and only inside its `writes:` scope.
9. LiteLLM exposes no per-model in-flight gauge. Our own counter is
   exact for our own runs; the proxy-wide rate comes from two samples
   of `/metrics/`. `router/snapshot.json` every 15 s.

## Gaps

All ten are decided by the user. Full text with the reasoning:
`design-options.md` §11. Recommendation in the last column.

| # | Question | Options | Rec |
|---|---|---|---|
| Q1 | Board location and scope | (a) `.swarm/` at the repo root, one repo; (b) inside the ticket dir, one board per ticket; (c) a state dir outside the repo, keyed by repo hash | a |
| Q2 | How many actuator processes | (a) one, slots in-process; (b) N, one per type, popping by rename; (c) one plus on-demand slot helpers | a |
| Q3 | Repo write conflict policy | (a) strict `writes:` scope exclusion at dispatch; (b) optimistic overlap with snapshot and restore; (c) one global write lock for `implement` | a |
| Q4 | A chem whose producers all fail | (a) locked-state detector starts one capped `unblock` agent; (b) the chem degrades to best-effort; (c) the actuator re-enqueues the failed producers by itself | a |
| Q5 | Stop rule | (a) one goal check when the board empties, then exit; (b) goal check, repair tasks, repeat up to `max_rounds`; (c) no goal check | a |
| Q6 | Can a plan change during a run | (a) immutable for the run; (b) versioned swap at a queue-empty boundary; (c) fragment union over a plan directory | a |
| Q7 | Commit policy | (a) one commit per accepted task; (b) one commit per plan at the goal check; (c) no commits | b |
| Q8 | How an agent returns its result | (a) the whole final message, harvested; (b) a required fenced JSON block; (c) an outbox file | a |
| Q9 | Default concurrency and busy threshold | (a) 8 slots, 2 in flight per model, thresholds per §7.2; (b) 4 slots, raise after 10 clean runs; (c) derive the cap from `/health` quota at start | a |
| Q10 | Human gate | (a) none in v1; (b) gate on protected `writes:` scopes; (c) gate on cost above a threshold | a |

Q1 and Q3 block the board layout and the first slice. The other eight
can be taken with a default and revisited.
