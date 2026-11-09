# Wispies: design options (rev 2)

Status: design for review. No code.
Rev 1 is in `design-options-v1.md`. This revision applies the owner's
answers of 2026-10-30.

## 1. What changed from rev 1

| Rev 1 rule                                  | Rev 2 rule                                                                                    | Why                                                                           |
|---------------------------------------------|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| Git worktree and branch per candidate       | Feature flags and parameterization. Write-scope exclusion. Snapshot and restore of the scope. | Owner decision. A worktree copies the whole repo for a 5-minute task.         |
| Wispy runs each leaf task and distills it   | Wispies calls `wisp` directly. No distill.                                                    | Owner decision. A distill is a second model call. Wispies does not use wispy. |
| Role pools plus a seed task                 | One plan file. One actuator. No seed.                                                         | Owner decision. The plan defines the types, the goal, and the deliverable.    |
| Claim, lease, heartbeat, gc, reclaim        | None. The actuator is the only writer of board state.                                         | A hard timeout and one dispatch owner remove the need. See §6.                |
| A failed task returns to the queue          | A salvage session must enqueue tasks and finish. The task never returns to the queue.         | Owner decision.                                                               |
| `blocked-on: [task-id]`                     | Pheromones (chems). A task binds on named chems.                                              | Owner decision. A chem survives a decomposition.                              |
| A race of 3 worktrees                       | A parameter grid, or 3 flag-gated strategies in disjoint files.                               | Worktrees are gone.                                                           |
| The router scores `(model, thinking)` pairs | Each type holds a ladder. The router picks the first rung that is not busy.                   | Owner decision.                                                               |
| A pool process per role                     | One actuator process. Slots per type.                                                         | Fewer writers. Simpler protocol.                                              |

## 2. Terms

- **Board**: the `.swarm/` tree. The actuator is its only writer.
- **Plan**: one file. It holds the goal, the deliverable, the types,
  the ladders, the caps, and the root tasks.
- **Task**: one small unit of work. One task is one wisp session, plus
  at most one salvage session.
- **Type**: a role preset. It holds the capability set and the model
  ladder. Examples: `design`, `scout`, `implement`, `verify`.
- **Actuator**: the `wispies` executable. It holds the queue and the
  slots. It holds no plan.
- **Pheromone** (`chem`): a named file that records a finished
  contribution. A task waits on a set of chems.
- **Write scope**: the set of paths that a task may change. It
  replaces the worktree.

The design keeps the whole toolkit: a file protocol, git, and tests.
It drops the worktree.

## 3. Shape

### 3.1 One plan, one actuator

```
wispies run .swarm/plans/p-0001.toml
  load plan, validate it, append the root tasks to inbox/
  loop:
    scan inbox/                      # agents enqueue here
    dispatch ready tasks while a slot is free:
      choose the type, choose the ladder rung, build the capability set
      spawn: nono wrap <grants> wisp run ...  (one child process)
    reap children, harvest the result, flip chems, append the ledger
    when nothing runs and nothing is ready:
      if a chem is incomplete and all its producers are terminal -> unblock task
      elif no goal check for this round -> goal check task
      elif the goal is met -> write report/final.md, exit 0
      elif round < max_rounds -> next round
      else -> exit 2 with a report
```

The plan holds the plan. The actuator applies the plan's caps and the
board's reflexes. No process holds a global task graph in memory.

The actuator is the only writer of `work/`, `chems/`, `ledger/`, and
`report/`. Agents write only to `inbox/`. `nono` enforces this boundary
with a filesystem allow list.

### 3.2 The plan

```toml
id = "p-0001"
goal = "The retry path passes its acceptance test and the suite is green."
deliverable = "A committed change plus report/final.md."

[actuator]
slots = 8
context_guard = "70%"
max_minutes = 15            # wall clock per work session
salvage_minutes = 3         # wall clock for the salvage session
budget_usd = 20.0
sample_seconds = 15
max_unblocks_per_chem = 2
max_rounds = 3

[limits]
max_depth = 4
max_fanout = 5
max_tasks = 64

# One root task per plan is usual. A root task is data, not an agent.
[[tasks]]
id = "t-0001"
type = "design"
class = "design.split"
prompt = "Split the goal into tasks. Each task names one deliverable and one acceptance command."

# A type is a capability set plus a model ladder.
[types.design]
grants = { repo = "read", inbox = "write" }
class = "design.split"
ladder = [["Claude Sonnet 5", "high"], ["GLM 5.3", "high"]]
max_minutes = 10

[types.implement]
grants = { repo = "scope", inbox = "write" }
class = "code.edit"
ladder = [["DeepSeek V4.1 Flash", "xhigh"], ["GLM 5.3", "high"]]

[types.verify]
grants = { repo = "read", board = "read", inbox = "write", report = "write" }
class = "verify.gate"
ladder = [["DeepSeek V4.1 Flash", "high"], ["Qwen 3.8 27B", "off"]]

[types.judge]
grants = { repo = "read", board = "read", inbox = "write" }
class = "verify.judge"
ladder = [["Claude Sonnet 5", "high"], ["GLM 5.3", "high"]]
avoid_families = ["deepseek", "qwen"]   # independence from the candidates
```

A plan is data. A designer can write a new plan, and the operator runs
it. A plan is not a task type, so no agent can widen its own rights.

### 3.3 Task lifecycle

Five states. The state is a field in `work/<id>/meta.json`, written by
the actuator only.

| State | Meaning |
|---|---|
| `running` | One wisp session is live, or the salvage session is live. |
| `done` | The session ended with exit 0 and a harvested result. |
| `split` | The task ended, and it enqueued successors. The successors carry the work. |
| `failed` | The session ended without a result and without successors. |
| `stopped` | The actuator killed the task: budget, or a plan-level stop. |

The happy path:

1. The task sits in `inbox/<id>.md`.
2. Every chem in `binds` is complete. No other running task holds an
   overlapping write scope. A slot is free. The budget allows it.
3. The actuator renames `inbox/<id>.md` to `work/<id>/task.md`. The
   rename is the dispatch. It has one writer, so no lock is possible.
4. The actuator builds the system prompt from the type, opens
   `wisp new --name <id>`, then runs `wisp run` under `nono` and a wall
   clock timer.
5. The session ends. The actuator harvests the final message into
   `work/<id>/result.md`, writes `meta.json`, appends `ledger/runs.jsonl`.
6. If the task has `emits`, the actuator writes `chems/<name>/<id>`.
7. The actuator validates the tasks that the agent enqueued. A
   successor is a new `inbox/` file whose id starts with the parent id
   (`<parent>-<n>`). A task may also enqueue work that is not its own
   successor; the actuator accepts it either way. A rejected successor
   goes to `archive/rejected/` with the reason.

The failure path:

1. The session hits the wall clock, hits the context guard (exit 75),
   or dies on an API error.
2. The actuator writes the stop reason in `meta.json`, then starts the
   **salvage session**: same task id, a fresh dir `runs/<id>-salvage`,
   `salvage_minutes`, and a capability set that is `inbox` write plus
   read on the predecessor's session dir. The repo is read only.
3. The salvage prompt is fixed: "Your predecessor stopped at N minutes
   with reason R. Read its session at `<dir>`. Enqueue 1 to 4 tasks that
   finish this work. Carry the emit obligation `X`. Then finish. Do not
   do the work." The read grant on the session dir is what makes the
   successors able to continue: the transcript is the handoff.
4. If the salvage session enqueues successors, the state is `split`.
   The actuator copies the parent's `emits` onto the successors and adds
   them as producers of that chem. If it enqueues nothing, the state is
   `failed`.

The task never returns to the queue for its own work. A retry is a new
task id with `retry_of: <old id>`. The actuator creates that task by
itself in one case only: a transport error before the first round, when
no work product exists and no round is committed.

### 3.4 Types and capability grants

A type maps to a `nono wrap` invocation. The grant table is the whole
security model.

| Grant | nono flag | Effect |
|---|---|---|
| `repo = "read"` | `-r <repo>` | The agent can read the tree and cannot change it. |
| `repo = "scope"` | `-r <repo>` plus `-a` on each path in `writes:` | The agent can change only its declared paths. |
| `inbox = "write"` | `-a <board>/inbox` | The agent can enqueue tasks. |
| `board = "read"` | `-r <board>` | The agent can read results and chems. |
| `report = "write"` | `-a <board>/report` | The verifier can write a verdict. |
| Network | (always open) | Wisp needs the LLM proxy, so no type can be offline. `nono` has a filtering proxy mode if this becomes a problem. |

The session dir is always granted read and write, because wisp writes
`wisp.jsonl` there. The actuator creates it first.

A concrete spawn:

```
nono wrap -r /repo -a /repo/src/client -a /board/inbox -a /swarm/runs/t-0007 \
  wisp run -d /swarm/runs/t-0007 --context-guard 70%
```

The result of a read-only type is its final message. The actuator
harvests that message into `work/<id>/result.md`. The agent therefore
needs no write access to deliver a design, a scout report, or a
verdict. Only an `implement` type needs repo write access, and only
inside its scope.

#### 3.4.1 What nono enforces on this host

Tested on 2026-10-30 with nono v0.80.0. These facts change the spawn
line and the plan:

1. **The sandbox is real.** Landlock V6 is detected and enforced. A
   read of a path outside the grants fails with `Permission denied`.
   A write outside the grants fails the same way. So `-r <repo>` is
   required for every type, and a missing grant is a hard failure, not
   a warning.
2. **Non-interactive mode requires `--allow-cwd`.** Without it, nono
   exits before the child starts. It auto-includes the cwd with read
   access only. The actuator passes it and closes the gap with
   explicit grants.
3. **The default profile grants write on `/tmp`,** and read on
   `/usr`, `/etc/ssl`, and the resolver files. So the board must not
   live under `/tmp`: a grant there would be a no-op. Task scratch
   space must be granted explicitly, and it must not be `/tmp`.
4. **A grant on a path that does not exist does nothing.** Nothing
   fails; the process just gets no access. The actuator must reject a
   `writes:` entry whose path is absent, and it must create a missing
   parent directory before the run when the plan allows it.

### 3.5 Waiting: pheromones

An agent cannot wait. It enqueues and finishes. Waiting is a board
state, not an agent state.

A chem is a named contribution. Two files describe it:

```
chems/<name>.want          # {"producers": ["t-0010", "t-0011", "t-0012"], "why": "..."}
chems/<name>/<task-id>     # written by the actuator when that task ends done
```

The actuator owns both files. The rules are small:

1. When a task with `binds: [x]` is validated, the actuator creates
   `chems/x.want` with an empty producer list when the file is absent.
2. When a task with `emits: [x]` is validated, the actuator adds its id
   to `x.want.producers`.
3. The chem is complete when it has at least one producer and every
   producer has a file in `chems/x/`.

The `.want` file is monotonic: the actuator only adds producers. That
keeps the file valid without a lock. Rule 3's "at least one producer"
stops a typo from making a binder run early on an empty chem.

A task states `binds: [chem, ...]` and `emits: [chem, ...]`.

A race with three strategies:

```
t-0010  implement  binds: [params]   emits: [impl-fixed]   writes: [src/retry/fixed.py]
t-0011  implement  binds: [params]   emits: [impl-exp]     writes: [src/retry/exp.py]
t-0012  implement  binds: [params]   emits: [impl-jitter]  writes: [src/retry/jitter.py]
t-0020  verify     binds: [impl-fixed, impl-exp, impl-jitter]   emits: [bench]
```

`t-0020` becomes ready only when all three chems are complete. The
three implementers never block. When `t-0011` hits its wall clock, its
salvage session enqueues two smaller tasks, and the actuator copies
`emits: [impl-exp]` onto both. Both then become producers of
`impl-exp`, and `t-0020` still waits for the whole contribution, not
for one session.

This is the whole wait mechanism. No polling, no timeouts on
dependencies, no reaper over a dependency graph.

### 3.6 Locked state

A board state is locked when no task is ready, no task is running, and
at least one chem is incomplete although every one of its producers is
terminal.

The actuator then starts one `unblock` task. Its prompt carries the
chem name, the producer results, and the producer session dirs. The
agent has three ways out: it emits the chem itself, it enqueues
replacements that inherit the obligation, or it reports that the goal
is unreachable. The cap `max_unblocks_per_chem` (default 2) stops a
loop. After the cap the actuator writes a report and exits 2.

A locked board is a real defect in the design of the plan. The unblock
task exists to convert a silent hang into one more cheap session.

### 3.7 Evolution without worktrees

Three mechanisms, in increasing cost. The plan picks one per task.

**M1. Parameter grid (cheapest, default for tuning).**
One implementation supports a flag with N values. One `bench` task
runs the acceptance command once per value and reports the table. The
winner is a value in a config file. No file conflict is possible,
because the candidates are values. Cost: N test runs and one session.

```yaml
params:
  retry.backoff: [fixed, exp, jitter]
  retry.max: [3, 5, 8]
```

**M2. Flag-gated strategies (default for `candidates: 3`).**
Three implementers each write one strategy module in its own new file.
Discovery is by directory convention (`src/retry/strategies/*.py`
loaded by name). No shared registry file, so no edit conflict. The
`bench` task runs the suite with each strategy selected by an env var
or a config key. A `select` task sets the default. A `drop` task
deletes the losers, or moves them to `archive/strategies/`.

The one rule that makes M2 safe: **each candidate owns new files plus
at most one line in a config**, and the config line is written by the
actuator-driven `select` task, not by the candidates.

**M3. Serialized attempts in one scope (fallback).**
When two approaches must touch the same file, they cannot run at the
same time. The actuator serializes them by write scope. Each attempt
runs the gate before the next one starts. The actuator snapshots the
scope before each attempt and restores it when the gate fails.

Why 3 candidates: with one attempt a bad approach is invisible. With
two, a tie has no tiebreak. Three allows one gate failure, one correct
but costly candidate, and one best trade-off. Use 1 for mechanical
tasks, where the gate is exact.

No worktree is used in any of M1, M2, or M3.

### 3.8 Write-scope exclusion and the snapshot

`writes:` in the task contract is a list of path prefixes. The
actuator keeps the scopes of all running tasks. A dispatch is refused
if a new scope overlaps a running scope. Prefix matching only: no glob
engine, no `**`, no surprises.

A read-only task never conflicts.

When the plan sets `snapshot = true` for a type (default for
`implement`), the actuator copies the declared scope to
`work/<id>/pre/` before the run. A failed gate restores it with a
copy back. The copy is bounded by the scope, so it costs seconds, not
a full checkout.

The guard that a worktree gave us was "a failed candidate cannot
damage the tree". Two smaller guards replace it: the scope cap, and
the snapshot.

### 3.9 Goal check and stop rule

When no task is ready and no task is running, the plan's goal check
runs. The goal check is a `verify` type task with the `goal` and the
`deliverable` in its prompt. It reads the board and the repo, then
emits one of two chems: `goal-met` or `goal-gap`.

- `goal-met` stops the run with exit 0 and writes `report/final.md`.
- `goal-gap` starts a new round. The verifier enqueues the repair tasks
  it needs. The actuator applies `max_rounds` and the budget.
- After `max_rounds` the run stops with exit 2 and a report that names
  the open gaps.

The goal check is a task, not a process. It has the same rights as any
verifier. It cannot widen its own scope.

## 4. Board layout (answers 5.1)

Rev 1 layout was built for concurrent writers. Rev 2 has one writer.
It shrinks.

```
.swarm/
  plans/p-0001.toml
  inbox/<task-id>.md              # agents write here. The actuator moves out.
  work/<task-id>/
    task.md                       # the contract, after the dispatch rename
    result.md                     # the harvested final message
    meta.json                     # type, rung, start, end, exit, tokens, cost, stop reason
    pre/                          # the scope snapshot, when enabled
  chems/<name>.want
  chems/<name>/<task-id>
  runs/<task-id>/                 # the wisp session dir (WISP_SESSIONS_ROOT=.swarm/runs)
  runs/<task-id>-salvage/         # the optional salvage session
  runs/_board-<plan>/             # one wisp session that is never run: the parent of all task sessions
  report/<round>-goalcheck.md
  report/final.md
  ledger/runs.jsonl
  archive/rejected/  archive/dropped/  archive/claims/ (gone)
```

Removed from rev 1, with the reason:

| Rev 1 piece | Status | Reason |
|---|---|---|
| `claim/` directory | gone | One dispatcher. The dispatch is an in-process pick plus a rename. |
| `slots/` | gone | The slot count is a counter in one process. |
| `events.jsonl` | gone | `meta.json` and `ledger/runs.jsonl` hold the same data. |
| `ledger/reserved/` | gone | Reservation is an in-memory sum over the running tasks. |
| `children` file | gone | Derived from the `parent` field. |
| `work/` worktree | gone | Replaced by `writes:` scopes and flag-gated strategies. |
| `verdict.md` | gone | A verifier result is a `result.md`. |
| `config.toml` | gone | The plan holds the knobs. |
| `board/tasks/<id>/` | gone | `inbox/` then `work/<id>/`. Two places, not three. |

Two notes on wisp:

1. `WISP_SESSIONS_ROOT=.swarm/runs` gives one flat dir per session,
   named by task id. `wisp ls --tree` then works over the whole run.
2. `wisp new --parent` appends to the parent's `children` list with
   last-writer-wins. Concurrent `wisp new` calls can lose a link. The
   board must not depend on that list. The board uses the `parent`
   field of the task contract. `wisp ls --tree` is a convenience only.

## 5. Task contract (answers 5.2)

```yaml
---
id: t-0011
type: implement                 # a key under [types] in the plan
class: code.edit                # router work class
parent: t-0001
depth: 2
binds: [params]                 # start only when these chems are complete
emits: [impl-exp]               # contributions this task must produce
writes: [src/retry/exp.py]      # write scope. Overlap blocks a dispatch.
reads: [repo, work/t-0010]      # extra hints for the prompt builder
candidates: 1                   # 1 = plain task, 3 = expand to 3 strategies
params: {retry.backoff: exp}    # the parameter grid, when used
budget:
  max_minutes: 15
  max_cost_usd: 0.60
accept:
  - "pytest tests/test_retry.py -q"
retry_of: null
---
## Context
## Deliverable
## Verification
## Notes
```

Field notes:

- `id` is `<parent>-<n>`, or `<parent>-<rand4>` when the enqueuer cannot
  count safely. The actuator rejects a duplicate id.
- `type` must exist in the plan. A task cannot name a type that the plan
  does not define. This is the only rights boundary that matters.
- `depth` is set by the actuator, not by the agent. The agent's value is
  ignored. The actuator refuses a task past `max_depth`.
- `binds` and `emits` are the wait mechanism (§3.5).
- `writes` is the only field with a conflict rule (§3.8).
- `budget.max_minutes` cannot exceed the type limit. `max_cost_usd` is a
  hint for the kill check at a round boundary.
- `accept` is one shell command per entry. A verifier type runs these.
  A worker never grades itself.
- There is no `status` field. The state is in `meta.json`, owned by the
  actuator.
- There is no `blocked-on` list of task ids. A task id is unstable under
  decomposition; a chem name is stable.

## 6. Atomic rules (answers 5.3)

The short answer: rev 1 carried a claim protocol because rev 1 had two
or more pools that could claim the same task. Rev 2 has one actuator.
Most of §5.3 of rev 1 is deleted, not tuned.

### 6.1 Do we need the heartbeat?

No.

The heartbeat existed to answer "is the owner of this claim alive?"
from a *different* process. In rev 2 the owner is the actuator, and the
session is its direct child. Liveness is `waitpid`, the exit code, and
a wall clock timer. Those cost nothing and cannot be stale.

The `wisp.jsonl` mtime was a good free signal. It is not needed,
because no second process needs to judge the run.

### 6.2 Is reclaim necessary?

No.

Reclaim existed to steal a task from a dead owner. In rev 2 a task is
never owned twice:

- The dispatch is a rename by the single writer. A task cannot be
  dispatched twice.
- A dead session is not a stuck task. It is a known end state, and the
  actuator writes it immediately.
- The work that a dead session did not finish comes back as *new tasks*
  from the salvage session, not as a reclaimed task.

The cost of this choice is one extra cheap session per failure. The
gain is that the board has no lock, no lease, no pid check, and no gc.

### 6.3 What did each rev 1 mechanism guard?

| Rev 1 mechanism | The risk it guarded | In rev 2 |
|---|---|---|
| `mkdir claim/` | Two pools run the same task. | Impossible: one dispatcher. |
| `lease_until` and pid check | A dead owner holds a task forever. | Not needed: the owner is a child process with a timeout. |
| `wispies gc` | Stale locks accumulate. | Not needed: no locks exist. |
| Atomic `result.md` (temp, fsync, rename) | A reader sees a half-written result. | Removed: the actuator writes the result after the process ends, and it is the only reader. |
| Temp and rename for `task.md` | Two agents write one task. | Removed: the actuator owns every task file after dispatch. |
| Split caps in the board | A token fire from a splitting agent. | **Kept.** The actuator validates depth, fanout, total count, type, scope syntax, and one acceptance command. |
| `status` field with rename writes | Two writers disagree on the status. | Removed: the state is one field in `meta.json`, one writer. |
| `events.jsonl` | Audit and a status view. | Replaced by `meta.json` plus the ledger (§6.5). |

The only mechanism that survives is the split validation, because it
guards cost, not a race.

### 6.4 What atomic rules remain?

Three, and all three are about the agent-to-board handoff:

1. **Enqueue is a temp file plus rename.** The agent writes
   `inbox/.tmp-<rand>` and renames it to `inbox/<id>.md`. The dot
   prefix keeps an unfinished file out of the scan. `nono` grants write
   on `inbox/`, so the rename works inside the sandbox.
2. **The scan ignores dotfiles, and validates before it moves.** A
   malformed contract goes to `archive/rejected/` with the reason. It
   never enters `work/`.
3. **Task ids include randomness when the enqueuer cannot count.**
   `rename` overwrites silently, so a duplicate id must be prevented by
   construction, not by a lock.

Everything else is single-writer and needs no rule.

### 6.5 What are events here?

In rev 1 an "event" was one JSON line in an append-only audit stream,
which `wispies status` read to rebuild state. That was a second source
of truth beside the claim directory.

In rev 2 there is no event stream. There are three records, each with
one writer and one purpose:

- `work/<id>/meta.json`: one task. Type, rung, start, end, exit code,
  stop reason, tokens, cost, state.
- `ledger/runs.jsonl`: one line per session, appended by the actuator.
  This is the router's history and the cost report.
- `runs/<id>/`: the wisp session. The transcript and the exact prompt.
  This is the audit trail.

A status command reads `meta.json` files and the ledger. It does not
replay a stream. If a live view is needed, the actuator writes
`report/live.json` every `sample_seconds`; it is a cache, never a
source.

## 7. Router: the per-type ladder

### 7.1 Ladder

Each type holds an ordered list of `[model, thinking]` rungs. The
router walks it and takes the first rung that is not busy. When every
rung is busy, it takes the least loaded rung. This is the owner's
rule, and it is the whole router.

```toml
ladder = [["DeepSeek V4.1 Flash", "xhigh"], ["GLM 5.3", "high"], ["Qwen 3.8 27B", "off"]]

# Optional: a finer split by work class. The task's `class` picks the list.
[ladders]
"code.edit"  = [["DeepSeek V4.1 Flash", "xhigh"], ["GLM 5.3", "high"]]
"code.read"  = [["Qwen 3.8 27B", "off"], ["DeepSeek V4.1 Flash", "off"]]
"test.write" = [["DeepSeek V4.1 Flash", "high"]]
```

A type without a `[ladders]` table uses its single `ladder`. This is
the "optimized by work class" of the ticket: the class is the key, and
the class is also the key of the outcome EWMA.

Constraints are checked before the busy test: the model must hold the
estimated context with 15% headroom, must support tools, and must
accept the thinking level. A rung that fails a constraint is skipped.

For a `judge` type, `avoid_families` removes rungs from the
candidates' model families. The actuator checks this at dispatch, so a
plan cannot ask for a judge that is a candidate's twin.

### 7.2 The busy test

A rung is busy when any of these is true:

| Signal | Threshold | Source |
|---|---|---|
| Our own in-flight on this model | `>= max(2, slots/4)` | The actuator's own counter. Exact, free. |
| Proxy rate ratio | `rpm / rpm_limit > 0.7` | Two samples of the LiteLLM counters. |
| Queue or TTFT | `> 2x` the model's own EWMA | The same samples. |
| Error rate | `> 5%` over the last 20 runs | `ledger/runs.jsonl`. |
| Recent local failures | 3 failures in a row on this model | The ledger. |

The first signal is the most useful and it needs no network call. It is
the "busy" that the owner asked for.

### 7.3 Where the load signal comes from

`router/snapshot.json` is written by the actuator every
`sample_seconds` (default 15) from three endpoints:

| Endpoint | Size | Use | Cache |
|---|---|---|---|
| `GET /health` | ~6 kB | Healthy endpoints, Azure remaining request and token quota. | 15 s |
| `GET /metrics/` | ~12.8 MB | Global in-flight, per-deployment rpm, failures, TTFT, queue. Derive the rate from two samples. | 15 s |
| `GET /v1/model/info` | ~254 kB | Price, context, tool support, reasoning support. | 1 day |

There is no per-model in-flight gauge in the proxy. Two rules compensate:

1. Our own counter gives per-model in-flight exactly, for our own work.
2. The rate ratio from two counter samples gives the proxy-wide
   pressure per model.

A snapshot older than `3 * sample_seconds` is stale. A stale snapshot
means "no load data". The busy test then uses only the local
signals: our in-flight count and the ledger. The routing never blocks
on metrics.

### 7.4 Admission control

If every rung of the type is busy and the deadline allows, the
actuator holds the task for one `sample_seconds` tick before dispatch.
If the total in-flight proxy-wide is above a cap, the actuator runs
fewer slots than `slots`. That is the backpressure.

## 8. Knobs

All knobs live in the plan. CLI flags override them for a run.

| Knob | Default | Effect |
|---|---|---|
| `slots` | 8 | Total live sessions. |
| `slots` per type | 0 = no limit | Per-type cap. Replaces `role_concurrency`. |
| `context_guard` | `70%` | Passed to every `wisp run`. |
| `max_minutes` | 15 | Wall clock per work session. |
| `salvage_minutes` | 3 | Wall clock for a salvage session. |
| `max_depth` | 4 | Split depth cap. |
| `max_fanout` | 5 | Children per task. |
| `max_tasks` | 64 | Total tasks per plan. |
| `budget_usd` | 20 | Global spend cap. |
| `max_rounds` | 3 | Goal check rounds. |
| `candidates` | 1 | Minimum for a race is 3. |
| `sample_seconds` | 15 | Snapshot and live report interval. |
| `route_command` | null | Replaces the ladder walk with an external command. |

The `route` hook stays. It reads the task and the snapshot on stdin and
writes `{model, thinking, reason}`. The local ladder is the default
and the fallback.

## 9. Failure modes and guards

| Failure | Guard |
|---|---|
| An agent edits outside its scope | `nono` denies the write. The denial is logged. |
| Two tasks change one file | Write-scope exclusion at dispatch. |
| A bad edit stays in the tree | Scope snapshot, restore on a failed gate. |
| A session hangs | Wall clock kill, then the salvage session. |
| A session hits the context guard | Exit 75, then the salvage session. |
| A task splits without limit | Depth, fanout, total count, and type validation. |
| A chem never completes | Locked-state detector plus `unblock`, capped at 2. |
| Budget overrun | In-memory spend plus reservation, checked before dispatch and at each round boundary. |
| A dead session loses its work | The salvage prompt points at the session dir, so the successor tasks read the transcript. |
| A model is down | Ladder walk skips a busy or failing rung. |
| The snapshot is stale | Local signals only. |
| Self-grading | Separate `verify` type, separate session, `avoid_families`. |
| An enqueued task is malformed | Validated at the scan, moved to `archive/rejected/`. |
| The actuator restarts | `work/*/meta.json` without an end time is marked `failed` with reason `actuator-restart`. No adoption, no zombie claims. |
| An agent writes a duplicate id | Ids carry a random suffix; the scan also rejects a duplicate. |

## 10. Rollout

1. **Loop.** Plan loader, inbox scan, one `implement` type, `nono`
   grants, harvest, ledger, wall clock, salvage. A test with three
   tasks, one that times out. No chems.
2. **Chems and the split.** `design` and `verify` types, the chem
   files, the locked-state detector, split validation, the goal check.
   A test with a designer that splits to three tasks and a verifier
   that binds on three chems.
3. **Ladder.** The snapshot sampler, the busy test, the ledger EWMA.
   A test with a stale snapshot and a busy first rung.
4. **Evolution.** The parameter grid, the flag-gated strategies, the
   `bench` and `select` tasks. A test with three strategies and one
   that fails the gate.
5. **Observability.** `wispies status`, `wispies report`, a live
   `report/live.json`, 8 slots and 4 types.

The order matters. Chems come before evolution, because a race is a
chem problem before it is a selection problem.

## 11. Open questions

Each question has three alternatives. The recommendation is marked.

### Q1. Where does the board live, and what does one board cover?

- **A. `.swarm/` at the repo root, one board per repository.**
  The board is a sibling of the code. One plan covers one repo. The
  scope is a path prefix, so it is meaningful. `.swarm/` goes into
  `.gitignore` except `plans/` and `report/`. *(recommended)*
- **B. One board per ticket, inside the ticket dir.**
  The board travels with the human record. A multi-repo task is
  impossible. The path prefixes need a repo prefix.
- **C. A state dir outside the repo, one board per repo hash.**
  The repo stays clean. `wispies` runs from anywhere. The board is
  less discoverable, and a worktree-free design does not need it.

Sub-question, same three answers: one repo, one ticket, or many repos.
A multi-repo plan would need a `repo:` field per task and a per-repo
scope table. That is a second feature. Recommendation: one repo first.

### Q2. How many actuator processes?

- **A. One process per plan, slots in-process.** *(recommended)*
  No locks anywhere. The simplest correct thing. The process is the
  unit of restart.
- **B. N processes, one per type, popping from `inbox/` by rename.**
  Independent failure domains and a true M:N schedule. A rename is
  already atomic, so a lost race is `ENOENT`. Cost: shared budget and
  shared scope table need a lock.
- **C. One main process plus a helper that starts extra slots on
  demand.** Good for bursty load. Cost: the scope table and the budget
  must be shared, so this becomes B in disguise.

### Q3. What is the conflict policy for repo writes?

- **A. Strict scope exclusion.** *(recommended)*
  Overlap blocks a dispatch. Predictable. Cost: a race on one file is
  serialized.
- **B. Optimistic overlap with a snapshot and a gate.** Two tasks may
  touch one file. The actuator snapshots both and restores the loser.
  Cheaper for exploration, but a restore can undo the winner's edit.
- **C. One global write lock for `implement`.** Fully serial code
  writes, parallel everything else. Trivial to reason about, and slow.

### Q4. What happens when a chem's producers all fail?

- **A. The locked-state detector starts an `unblock` agent.**
  *(recommended)* The agent may emit the chem itself, may enqueue
  replacements, or may declare the goal unreachable. Capped at 2 per
  chem.
- **B. The chem degrades.** When every producer is terminal and the
  chem is incomplete, it becomes `best-effort`, and the binder starts
  with a warning in its prompt. Cheap, and it hides real failures.
- **C. The actuator repairs without an agent.** It re-enqueues the
  failed producers from their original contracts with `retry_of`. No
  model call to decide, but it repeats a failure that already happened.

### Q5. What is the stop rule?

- **A. One goal check when the board empties, then exit.** *(recommended
  for slice 1)* Simple, cheap, and easy to reason about.
- **B. Goal check, repair tasks, repeat, up to `max_rounds`.** The full
  loop. Better autonomy. Cost: rounds can oscillate.
- **C. No goal check.** The operator reads `report/final.md` and
  decides. Cheapest, and the swarm never says "done".

### Q6. Can a plan change during a run?

- **A. No. The plan is immutable for the run.** *(recommended)*
  A new plan is a new run with a new board directory or a new plan id.
  Deterministic and reproducible.
- **B. Versioned swap at a queue-empty boundary.** A `planner` task may
  write `plans/p-0002.toml`; the actuator loads it when the board
  empties. Adaptive, and two plans can disagree mid-run.
- **C. Fragment union.** The plan is a directory; any task with the
  `planner` right may drop a fragment. Most emergent, hardest to audit.

### Q7. Commit policy?

- **A. One commit per accepted task.** Best attribution and the easiest
  revert. Noisy history.
- **B. One commit per plan, at the goal check, with the report as the
  message.** *(recommended)* Clean history, one recovery point, and
  the report explains the change.
- **C. No commits.** The working tree is the product; git is the undo
  for a human. Cheapest, and it loses attribution.

### Q8. How does an agent return its result?

- **A. The whole final message, harvested by the actuator.**
  *(recommended)* Zero agent-side machinery; works for read-only types.
  Weak structure.
- **B. A fenced ` ```result ` JSON block, required.** Machine-readable
  and validatable. Cost: a malformed block fails a whole session.
- **C. An outbox file.** The agent writes `outbox/<id>.json`; the
  contract is the file, not the transcript. Explicit, and it needs
  another nono grant.

### Q9. What default concurrency, and which busy threshold?

- **A. 8 slots, at most 2 in flight per model, thresholds as in §7.2.**
  *(recommended)* Measured once, then tuned.
- **B. 4 slots to start, raise after 10 clean runs.** Conservative. It
  costs wall clock on every run.
- **C. Derive the cap from `/health` remaining quota at start.** Adapts
  to the day. It couples a plan run to proxy internals.

### Q10. Does any task class need a human gate?

- **A. No gate. The plan and the goal check are the gate.**
  *(recommended for the first version)* The swarm runs unattended.
- **B. A gate on protected scopes.** A `writes:` entry may be marked
  `protected`; a task that touches one stops at `review` and waits for
  a file to appear (`.swarm/report/approve-<id>`). One human step per
  risky change.
- **C. A gate on cost.** Any task above `gate_usd` waits for approval.
  Good for a shared proxy budget, and it gates the wrong thing when
  the risk is correctness.

## 12. Goal coverage

| Ticket goal | Mechanism |
|---|---|
| Parallel | `slots` live sessions, one wisp child each, plus per-type slot caps. |
| Typed | Types hold the capability set, the ladder, and the limits. `nono` enforces the capability set. |
| Emergent | Any task may enqueue. The graph grows from local decisions. The plan holds a goal, not a graph. |
| No top-level orchestrator | The actuator holds the queue and applies the plan. It holds no plan of its own and makes no design decision. |
| Designers split | A `design` type writes child contracts with one deliverable and one acceptance command each. The actuator validates the split. |
| Evolutionary | M1 parameter grid, M2 flag-gated strategies, M3 serialized attempts. A `bench` task measures, a `select` task decides. No worktrees. |
| Optimized model and thinking | A per-type ladder, the busy test, the snapshot, the ledger EWMA. |
| Small and fast | One session per task, a wall clock cap, no distill, no worktree, leaf results as text. |
| Ephemeral | The session ends and the task leaves the queue. Evidence stays in `runs/` and `work/`. |
| Filesystem exchange | Task contracts, results, chems, the ledger, and the reports are files. |
| Top-level knobs | The plan file (§8). |
