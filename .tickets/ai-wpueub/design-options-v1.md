# Wispies: design options

Status: draft for review. No code yet.

## 1. Purpose

Wispies is a swarm of short-lived agents. Wisp runs one agent. Wispy
wraps one ticket around wisp sessions. Wispies adds three things:

- many wisp sessions run at the same time;
- typed agents with different rights and different model classes;
- a shared filesystem board that agents use to claim, split, verify,
  and select work.

The board is the only shared authority. No agent holds the global plan.
The pool that starts processes is an actuator, not a planner.

## 2. What wisp and wispy already give us

These facts shape the design. They come from the source.

| Fact | Consequence |
|---|---|
| `wisp new` fixes the model and the system prompt for the session. | Model routing is a session-creation decision. No mid-session re-route. Good: one session = one work class. |
| Wisp has no temperature knob. It sends `model`, `thinking`, `tools`. | Candidate diversity must come from different approach seeds, different models, or different context packs. |
| Wisp has no API retry. A failed request ends the run. | The pool owns retry and fallback. Wisp stays simple. |
| A completed round is committed to `wisp.jsonl` as it ends. | `wisp.jsonl` mtime is a free heartbeat and a progress signal. No new hook is needed. |
| `wisp.usage` holds prompt and completion tokens plus cost data. | The router learns from real spend and outcomes. |
| `wisp.modelcfg` holds context size and price from `/v1/model/info`. | The router can read the same source. |
| Tools are bash and python3 only. | File protocol, git worktrees, and tests are the whole toolkit. |
| Session dirs are plain directories with a parent link. | A task can point at its exact run dir. Audit is free. |
| Wispy distills each work session into the ticket and `STATE.md`. | A distill is a second model call. Too heavy for a 5-minute task. Use it for design and close, not for every leaf. |
| Wispy binds one ticket and writes its status. | Fine for one ticket. A concurrent board needs its own claim protocol. |
| `tikit` stores extra frontmatter keys and queries them with SQL. | Tickets can carry `role`, `class`, `evolution`, `blocked-on`. |

## 3. Design axes

The design has five independent axes. Each has options. Mix them.

### 3.1 Substrate: where the board lives

**Option A. Tickets all the way (wispy-native).**

Each task is a tikit ticket. `task.md` is `ticket.md`. The claim is a
`claim/` directory inside the ticket dir. A lane script loops over
ready tickets and calls `wispy run --skills <role>`.

- Good: small amount of new code; human-readable records; commit per
  task is natural; reuses wispy, tikit, and the skills catalog.
- Bad: wispy runs a distill for each task; the tikit ticket dir gains
  phase, state, responses, and skills that a small task does not need;
  concurrent status writes need care; SQL over 1000 ticket files is
  slow but possible.
- Best when: you want the first working swarm this week.

**Option B. File-per-task board and a thin runner (recommended).**

A dedicated `.swarm/` tree. Each task is a directory with `task.md`,
`claim/`, `result.md`, `events.jsonl`, and `work/`. A `wispies` CLI
does claim, finish, split, verify, and race. It calls `wisp new` and
`wisp run` as subprocesses. It does not call wispy for leaves. The
human-facing record can still live in tikit, linked by id.

- Good: claim, lease, budget, race, and result are first-class;
  small and fast; no distill cost; easy to inspect with `ls` and
  `cat`; a single Python file can follow the wisp style.
- Bad: new tool to write and test; duplicates part of tikit.
- Best when: the swarm is the product, not a one-off.

**Option C. SQLite board, file artifacts (strongest correctness).**

One SQLite file holds tasks, claims, leases, attempts, and events.
Workers write artifacts to normal files. `sqlite3` transactions give
atomic claim, lease expiry, and ready queries.

- Good: no lock races; strong queries; easy metrics; crash-safe.
- Bad: the coordination state is not directly readable with `cat`;
  a database becomes a shared central component; NFS is risky;
  slightly against the "everything is a file" spirit.
- Best when: the swarm runs on one host and grows past a few hundred
  tasks, or when claim races start to hurt.

**Verdict.** Start with B. Keep the task file format compatible with
tikit so that a task can be exported to a ticket. Move to C only if
the file protocol shows real contention. A plain append-only event log
without SQLite is not recommended: offset-based claims are harder to
get right than a directory lock.

### 3.2 Activation: what starts agents

**Option 1. Role pools (recommended).**

`wispies pool --role worker -n 4` loops: claim one ready task, run one
wisp, finish it, claim again. Run one pool per role. The operator sets
the pool sizes. The pool enforces the top-level concurrency knob.

- Good: simple; bounded concurrency; no process tree; a crash loses
  one task, not the swarm.
- Bad: a pool is a central actuator. It is not a planner, but it must
  run somewhere.

**Option 2. Recursive spawning.**

A worker starts its children as subprocesses and waits. The tree grows
from the root.

- Good: pure emergence; no pool.
- Bad: concurrency is hard to cap; a parent that dies takes its
  children with it; deep trees are hard to observe; orphan control is
  weak.

**Option 3. Hybrid: pools plus a seed (recommended shape).**

The operator creates one design task, or the root ticket already has
one. Designer pools start it. Designers split and exit. Worker and
verifier pools pick up the children. No process is permanent except
the pools. Designers bootstrap, and they are not a top-level
orchestrator: they make local splits and stop.

### 3.3 Agent lifecycle

**Option 1. One wisp session per task attempt (recommended).**

A task claim starts one `wisp new` + `wisp run`. The agent exits after
`result.md`. The context stays small. A guard stop means a failed
attempt, not a long resume chain.

**Option 2. One long session per role with steering.**

A worker session stays alive and receives tasks through `wisp steer`.

- Good: fewer session-creation calls.
- Bad: context grows; one task pollutes the next; the model cannot be
  re-routed; a crash loses the lane. Reject.

**Option 3. One session per candidate attempt, one per verifier.**

Same as option 1, with a candidate id. Use this for races.

### 3.4 Evolution: how the best solution wins

**Option 1. Parallel race plus judge (recommended default).**

The designer marks a task `evolution: 3`. The board expands it into
three candidate tasks with different approach seeds, plus one judge
task that is blocked on all three. Workers run the candidates in
separate git worktrees. The gate verifier runs the acceptance tests.
The judge ranks the passing candidates. A merge task applies the
winner.

- Good: true parallel search; independent evidence; the loser archive
  supports later synthesis.
- Bad: 3x cost; needs a judge rubric; needs worktree isolation.

**Option 2. Sequential hill climb.**

One worker attempts. A verifier writes repair tasks. Repeat up to K
rounds.

- Good: cheap; good for tasks with a clear failing test.
- Bad: no parallel exploration; local minima.

**Option 3. Tournament.**

Six candidates, pairwise elimination, then a final judge.

- Good: better selection with many candidates.
- Bad: cost and latency; most tasks do not need it. Use only when the
  solution space is wide and the payoff is high.

**Option 4. Island model.**

Several pools evolve solutions with rare migration.

- Good: diversity on hard design problems.
- Bad: too complex for the first version.

**Verdict.** Default 3 candidates for "solution-shaped" tasks. Set
`evolution: 1` for mechanical tasks (rename, bump, move). Let the
designer choose the count with a cost cap. Use hill climbing when the
gate fails with a clear error.

### 3.5 Router: how model and thinking are picked

**Option 1. Static table.**

`code.edit -> DeepSeek V4.1 Flash, thinking off`; `design.split ->
Claude Sonnet 5, thinking high`; and so on.

- Good: predictable, zero infrastructure, easy to reason about cost.
- Bad: ignores load and price changes; wrong on new models.

**Option 2. Load-aware cost/quality score (recommended).**

A black-box `route` command reads a snapshot of LiteLLM health and
metrics plus a local outcome ledger. It scores `(model, thinking)`
pairs for a work class and returns one. Fallback list included.

- Good: uses current load and real prices; learns from verifier
  outcomes; still simple enough to debug.
- Bad: needs a snapshot sampler and a quality prior.

**Option 3. Online bandit (UCB or Thompson).**

Explore models per class and exploit the best.

- Good: adapts to model changes and hidden quality.
- Bad: needs many trials; can pick a bad model early; hard to explain.
  Add it later behind the same interface.

**Option 4. External router service.**

Point the `route` hook at another team's optimizer.

- Good: pluggable; meets the black-box requirement.
- Bad: another service to run. Keep the local heuristic as the default
  and the fallback.

## 4. Recommended shape

Use B + hybrid pools + one session per attempt + race/judge + the
load-aware router.

```
Operator / CI
    |
    v
wispies bootstrap  --->  one design task (role=designer)
    |
    v
designer pool (1-2)  --split-->  worker tasks, verifier tasks
    |                                   |
    v                                   v
worker pool (4-8)  <---claim---  filesystem board  ---claim--->  verifier pool (1-2)
    |                                   |
    +--> result.md + candidate worktree |
                                        +--> verdict.md + repair tasks
                                        +--> winner + merge task
```

The pools hold no plan. They claim what the board offers for their
role. Any designer or worker can add tasks. Any verifier can add
repair tasks. The board applies the deterministic rules: lease expiry,
sibling completion, race expansion, budget stop.

### 4.1 Goal coverage

| Goal | Mechanism |
|---|---|
| Parallel | Independent role pools plus global slot locks. Each pool runs one wisp per slot. |
| Typed | Role personas with separate rights, skills, budgets, and model classes. |
| Emergent | Workers and verifiers create tasks. The task graph grows from local decisions. The board has no planner. |
| No top-level orchestrator | The pool is an actuator. Designers seed the graph. No process owns the plan. |
| Designers split | The designer skill writes a DAG of child tasks with one deliverable and one testable criterion each. Depth and fanout caps apply. |
| Evolutionary | A race task expands to at least 3 candidates in separate worktrees. A gate verifies. A judge ranks. The winner is merged. Losers are archived. |
| Optimized | The router scores `(model, thinking)` by work class, price, health, and load. It updates quality from verifier outcomes. |
| Small and fast | One wisp session per task attempt. Leaf tasks use `result.md`, not a wispy distill. Per-task token, time, and cost budgets. |
| Ephemeral | The agent exits after the result. Worktrees and session dirs stay as evidence. |
| Filesystem exchange | Task contracts, claims, results, verdicts, worktrees, and ledgers are files. |
| Top-level knobs | `concurrency`, `context_guard`, `lease`, `budget_usd`, `max_depth`, `max_fanout`, `min_candidates`, `sample_seconds`. |

## 5. Board protocol

### 5.1 Layout

```
.swarm/
  config.toml
  board/
    tasks/<task-id>/
      task.md              # contract, frontmatter + body
      claim/               # atomic lock directory; owner, lease, session
      result.md            # worker output contract
      verdict.md           # verifier output contract
      events.jsonl         # append-only audit; not the source of truth
      work/                # worktree, branch, or artifact dir
      children             # newline list of child ids, written by split
    slots/                 # global concurrency slots, optional
  runs/<task>-<attempt>/   # wisp session dirs, parent-linked
  archive/                 # losers, logs, superseded specs
  ledger/router.jsonl      # model, thinking, tokens, cost, outcome
  ledger/reserved/         # one reservation dir per live task
  router/snapshot.json     # cached LiteLLM health and metrics
```

Task ids: `<parent>-<n>` or a short random id. Keep them stable.
`runs/` uses the wisp session name `<task>-<attempt>` so a task maps to
its exact `wisp.jsonl`.

### 5.2 Task contract

```yaml
---
id: t-0007
name: "Add retry to the client"
role: worker              # designer | worker | verifier
parent: t-0003
blocked-on: [t-0005]
status: open              # open | claimed | review | done | split | blocked | failed | withdrawn
class: code.edit          # router work class
evolution: 1              # 1 or >=3
attempt: 0
producer: null
acceptance:
  - "pytest tests/test_retry.py exits 0"
  - "no public API change"
budget:
  max_tool_calls: 25
  max_tokens: 120000
  max_minutes: 20
  max_cost_usd: 0.50
rights:
  spawn_children: 2
  max_depth: 4
  write_worktree: true
---
## Context
## Inputs
## Deliverable
## Verification
## Notes
```

The status field is a cache for humans. The claim directory and the
result files are the truth. A stale status must never block a claim.

### 5.3 Atomic rules

- Claim: `mkdir tasks/<id>/claim` is atomic. Inside, write `owner`,
  `pid`, `session`, `lease_until`, `started`. The loser of the mkdir
  gets `EEXIST` and moves on.
- Heartbeat: no daemon. The pool checks two signals. First, the pid in
  the claim must be alive (`os.kill(pid, 0)`). Second, the mtime of
  `runs/<...>/wisp.jsonl` must be fresh. Wisp commits each finished
  round, so the mtime tracks progress. A live pid wins over an old
  mtime: a long model call must not lose its claim. The mtime is the
  signal when the pid is gone or the run is on another host. A claim
  with no session after `start_timeout` is expired. A claim with a
  dead pid and an mtime older than `lease` is expired. The pool always
  enforces the task `max_minutes` with a process timeout, so a live
  but hung pid cannot hold a claim forever.
- Reclaim: any pool process may run `wispies gc` before a claim. It
  renames an expired `claim/` to `archive/claims/<id>-<ts>/` and sets
  the task back to `open`. Use a guard file to make the rename
  single-winner. No separate reaper is needed.
- Finish: write `result.md` or `verdict.md` to a temp file, `fsync`,
  then `rename` into place. Then rename `claim/` out. A crash between
  the two leaves a result and a claim; gc sees the result and closes
  the task.
- Split: the parent writes `children`, writes each child `task.md`,
  then writes `split` to `result.md`. The board checks that the child
  count is within `max_fanout` and `max_depth`.
- Status changes: write a temp file and `rename`. Never edit a task
  file in place. Never let two agents write the same task.
- Events: one `os.write` of one JSON line with `O_APPEND`. Events are
  for audit and for `wispies status`. They are not the source of truth.

### 5.4 Ready rule

A task is ready when:

1. `status` is `open`;
2. `claim/` does not exist;
3. every id in `blocked-on` has a `result.md` with `status: done`;
4. the role pool has a free slot;
5. the global budget is not exhausted.

The claim check is authoritative. The rest is a hint.

### 5.5 Parent completion

When a child finishes, the board checks its parent. If all children
have `done` results and the parent is a race, it creates the judge
task. If all children are done and the parent has no judge, it marks
the parent `review`. This is a deterministic reflex. No agent decides
it. A verifier then claims the parent review task.

## 6. Roles

A role is a persona file, a skill list, a default work class, and a
set of rights. The runner composes the persona with
`wisp build-system-prompt --wisp --skills --agents-md` and passes it
to `wisp new -s`.

### designer

- Reads: parent spec, acceptance criteria, repository map, prior
  results.
- Writes: child `task.md` files, `plan.md`, `children`.
- Rights: create up to `max_fanout` children; no code edits; no
  verdicts.
- Must: give each child one deliverable and one testable acceptance
  criterion; declare dependencies; set `class`, `evolution`, and
  `budget`; refuse to create a child larger than the session budget.
- Model class: `design.split`. Strong model, high thinking.

### worker

- Reads: its own task, the inputs named by the task, the base commit.
- Writes: `result.md`, artifacts, candidate branch or worktree.
- Rights: edit its own worktree; spawn up to `spawn_children` children
  when the task is too large; never edit another task; never write a
  verdict.
- Must: run the named tests; report exact commands and exit codes;
  stop at the budget; write a result even on failure.
- Model class: from `class` (`code.read`, `code.edit`, `test.write`).

### verifier

Two sub-roles, same role with different skills.

- Gate verifier: runs acceptance tests in a clean copy; checks that
  the diff matches the task; records pass/fail with evidence. Cheap
  model, low thinking.
- Judge verifier: ranks candidates that pass the gate against a
  rubric; hides model identity; rejects self-grading. Strong model,
  high thinking, different model family from the candidates when
  possible.
- Rights: create repair tasks; select a winner; never edit a
  candidate.
- Model class: `verify.gate` or `verify.judge`.

Optional roles, only if needed: `scout` (collect context), `scribe`
(write the human ticket), `janitor` (gc). Start with three.

## 7. Splitting rules

The ability to split is the dangerous part. A split that is too fine
burns tokens. A split that is too coarse creates a task that cannot
finish in one session. Enforce these rules in the designer skill and
in the board:

1. One deliverable per task. One acceptance test set per task.
2. A leaf must fit one session budget: at most 25 tool calls, 120k
   tokens, 20 minutes, and the task budget.
3. A task that needs more than one file family or more than one
   concept is split.
4. Depth limit 4, fanout limit 5. A split past the limit is refused.
5. A worker may split once, and only when it has evidence: a file
   count, a failing test, or a missing dependency. It must write the
   evidence in `result.md`.
6. The board refuses a split with no acceptance criteria, with a
   cycle, or with a child that names a parent other than the splitter.
7. The total task count per root is capped (`max_tasks`, default 64).
   A designer that needs more must request a human decision.

## 8. Evolution protocol

1. The designer writes a race task with `evolution: 3` and one spec.
2. The board expands it into `c1`, `c2`, `c3`. Each candidate gets a
   different `approach_seed` in its task body and, optionally, a
   different model class. The spec is identical.
3. Each worker gets its own git worktree and branch. The base commit
   is recorded in `task.md`. No shared mutable workspace.
4. The gate verifier runs in a clean checkout of each candidate. A
   candidate that fails the gate is archived with its log. It cannot
   win.
5. The judge reads the spec, the gate evidence, and the diffs. It
   does not see model names. It writes a ranked list and a short
   reason for each rank.
6. The board writes `winner` and creates a merge task. The merge task
   applies the winner to the base branch. A second gate verifies the
   merge.
7. Losers stay in `archive/`. A `synthesis` task may read all diffs
   later. It is optional and costs another session.
8. If no candidate passes, the judge creates up to 2 repair tasks per
   candidate or one new design task. The race is bounded by
   `max_rounds` (default 2).
9. If the judge ranks two candidates as a tie, or if a second judge
   disagrees, the race escalates to a human decision. It does not
   spend a third judge by default. A tie is a signal that the spec or
   the rubric is weak.

Why at least 3: with one attempt, a bad approach is invisible. With
two, a tie has no tiebreak. With three, one can fail the gate, one can
be correct but costly, and one can be the best trade-off. Use 1 only
when the task is mechanical and the gate is exact.

## 9. Router

### 9.1 Contract (the black box)

Input, on stdin:

```json
{
  "class": "code.edit",
  "role": "worker",
  "est_input_tokens": 45000,
  "est_output_tokens": 4000,
  "needs_tools": true,
  "quality": "normal",
  "deadline_s": 900,
  "hints": {"language": "python", "risk": "low"}
}
```

Output, on stdout:

```json
{
  "model": "DeepSeek V4.1 Flash",
  "thinking": "off",
  "guard": "65%",
  "reason": "cheap, healthy, queue 0.2s",
  "fallback": ["Qwen 3.8 27B", "GLM 5.3 Flash"]
}
```

The default implementation is `wispies route`. Any command that reads
stdin and writes this JSON can replace it. It receives
`SWARM_SNAPSHOT` and `SWARM_LEDGER` as paths. This is the plug point
for another team's router.

### 9.2 What LiteLLM exposes today

I probed the company proxy with the existing `WISP_LLM_*` key. These
endpoints answer:

| Endpoint | Size | Contents |
|---|---|---|
| `GET /health` | ~6 kB | healthy and unhealthy endpoints; Azure `x-ratelimit-remaining-requests` and `-tokens` |
| `GET /v1/model/info` | ~254 kB | price per token, context window, max output, `supports_reasoning`, tool support |
| `GET /metrics/` | ~12.8 MB | global in-flight gauge; per-deployment request, failure, latency, TTFT, queue counters; rpm/tpm limits; deployment state |
| `GET /v1/models` | ~4 kB | model ids and context limits |
| `GET /router/settings` | ~9 kB | proxy routing strategy |

There is no per-model in-flight gauge. Derive the current rate from
two samples of the cumulative counters. For example, a 3-second sample
showed 40 rpm on `DeepSeek V4.1 Flash`, 40 rpm on `GLM 5.3`, 20 rpm on
the embedding model, and 20 rpm on `Claude Sonnet 5.5`, with 80 to 81
global in-flight requests. That is enough to rank load.

The metrics payload is large. Never fetch it per agent. A single
sampler writes `router/snapshot.json` every 15 seconds. All pools read
the file. A lock file stops duplicate sampling. If the snapshot is
stale, the router falls back to the static table. `/health` is cheap
enough to sample every 15 seconds too; `/v1/model/info` can be cached
for a day.

### 9.3 Scoring

For each allowed `(model, thinking)` pair:

```
quality  = prior[class][model]            # 0..1, from a table and EWMA outcomes
cost     = price_in * est_in + price_out * est_out
load     = f(rpm / rpm_limit, queue_s, ttft_s, error_rate, in_flight)
latency  = ewma_latency[class][model]
score    = quality - w_cost*cost_norm - w_load*load - w_lat*latency_norm
```

Constraints first: the model must be healthy, must hold the estimated
context with 15% headroom, must support tools, and must accept the
thinking level. Thinking levels are passed to the endpoint unchanged,
so keep a per-model allowed set. `off` means omit the field.

Priors by class are a small table. Outcomes update them with an EWMA:
a gate pass or a judge win raises the quality; an API error, a guard
stop, or a failed gate lowers it. The ledger holds one line per run.

Admission control: if all cheap models are above a load threshold and
the deadline allows, the pool waits instead of spending on an
expensive model. If the global in-flight count is above a threshold,
the pool reduces effective concurrency. This is the backpressure
knob.

### 9.4 Budget

- Each task reserves an estimate before the run. The reservation is a
  directory under `ledger/reserved/`. `mkdir` is atomic.
- The runner appends one JSON line with actual tokens and cost from
  `wisp usage` to `ledger/router.jsonl`. One `O_APPEND` write of one
  line is safe across processes.
- A task that exceeds `max_cost_usd` is killed at a round boundary.
- A global `budget_usd` stops new claims when spent plus reserved
  reaches the limit.
- `wispies status` derives spent and reserved from the ledger. No
  shared `spend.json` needs a write lock.
- Reservation is approximate. That is acceptable: the ledger is the
  truth after each run.
- If the proxy supports spend logs, the router may reconcile the local
  ledger against them. This is optional.

## 10. Top-level knobs

`swarm.toml`:

```toml
[swarm]
concurrency = 8
context_guard = "70%"
lease = "15m"
start_timeout = "2m"
max_depth = 4
max_fanout = 5
max_tasks = 64
budget_usd = 20.0

[roles]
designer = 1
worker = 5
verifier = 2

[evolution]
min_candidates = 3
max_candidates = 5
max_rounds = 2
keep_losers = true

[router]
command = "wispies route"
sample_seconds = 15
default_class = "worker.normal"
static_fallback = ["DeepSeek V4.1 Flash", "Qwen 3.8 27B"]
```

All are overridable by CLI flags. `--concurrency` is the global slot
count. `--guard` is passed to every `wisp run`. `--max-turns` maps to
`WISP_LLM_MAX_TURNS`. Per-task budgets are in `task.md`.

Concurrency is enforced in two layers:

- Pool size: each pool process runs at most one wisp at a time.
- Global slots: `board/slots/00..NN`. A claim needs a slot. `mkdir` is
  the lock. A slot holds a pid and a timestamp. `gc` frees a slot
  whose pid is gone or whose timestamp is old.

## 11. Failure modes and guards

| Failure | Guard |
|---|---|
| Two workers claim one task | `mkdir` claim is atomic; the loser backs off |
| Worker dies, task stuck | lease expiry plus opportunistic `gc` |
| Split explosion | depth, fanout, and task-count caps |
| Runaway cost | per-task reservation, global budget, kill at round boundary |
| Bad model choice | router fallback list; pool retries once with the next model |
| API error | runner marks `failed`, requeues once, then blocks |
| Context guard fires | task counts as failed; runner writes a partial result with the stop reason |
| Self-grading | separate verifier session; different model family; model identity hidden |
| Collusion through shared files | candidate worktrees; verifier sees only declared artifacts |
| Duplicate races | one race task id; board expands once; expansion marker |
| Stale snapshot | router uses static fallback; no blocking on metrics |
| One role starves | role pools are independent; verifier tasks have priority |
| Human cannot follow | `wispies status` and `wispies log`; events and wisp sessions |
| Proxy rate limit | `/health` remaining quota plus load score; admission control |

## 12. Rollout

1. Board protocol and `wispies task` commands. Tests: concurrent
   claim, lease expiry, atomic finish, split caps.
2. Pools and the three personas. One design task to three leaves, no
   evolution. This proves the loop.
3. Races and judging. Three candidates, gate, judge, merge. Tests:
   no gate pass, tie, judge independence.
4. Router snapshot and heuristic score. Tests: stale snapshot, missing
   model, context too small, fallback.
5. Observability: `status`, `log`, cost report. Stress run with 8
   workers and 2 verifiers.
6. Optional: SQLite board if contention, bandit if the ledger is rich
   enough, synthesis tasks if races show value.

## 13. Open questions

1. Substrate: do we accept a new `.swarm/` tree, or must the board be
   tikit tickets? Option B is my recommendation.
2. Scope of the swarm: one repository, one ticket, or many? This
   decides the worktree and merge design.
3. Is a pool process acceptable? It is an actuator, not a planner,
   but it is still one place that starts work.
4. Do we commit every task, or only the winner? A commit per task
   gives an audit trail and a recovery point. A commit per race is
   cleaner.
5. Should designers re-enter on a blocked task, or should a verifier
   create a new design task?
6. Which task classes get 3 candidates by default? My default: any
   task where the acceptance test can pass in more than one way.
7. Router: heuristic first, bandit later? Do we need per-user or
   per-team quotas on the shared proxy?
8. Human gate: does any class need approval before merge or close?
9. What concurrency is safe for the company proxy? The observed
   global in-flight was about 80 during this design. Start with 8 and
   measure.
10. Do we allow tasks with no deterministic gate (LLM judge only)? If
    yes, the judge needs a rubric and a stronger model.
