# kodama — round 2: one board, many wakes

Status: design for review. No code.
Round 1 is `design-options.md` (456 lines). This round applies the
owner's review of 2026-11-10. The five round-1 systems survive as
wake rules over one board, and four new wake rules join them. The type
system, the write scopes, and the config files do not survive.

## 0. Terms

- **kodama** — the root script. It holds no LLM. It spawns runs, takes
  locks, routes models, writes the ledger.
- **root** — one `kodama-sessions/` tree, one per project. One
  scheduler per root. Many roots share one PC and one machine-wide
  limiter.
- **agent** — a wisp session template under
  `kodama-sessions/agents/<name>/`. The template holds a system prompt
  (the persona) and a placeholder model. The template is the whole
  definition; no `agent.toml` exists.
- **spawn** — copy the agent template to
  `tasks/<id>/runs/<run>/`, rewrite the model in
  `wisp.run.json`, then run. A spawn is cheap and model-free until the
  copy is made.
- **run** — one short-lived wisp session: guard at most 50%, one
  artifact at most, one post at least.
- **task** — one submitted request. A task is a thread on the board
  and a directory with artifacts, runs, and a state.
- **board** — the append-only set of post files at the root. The
  board is the shared memory.
- **post** — one immutable JSON file written by a run through
  `kodama post`, `kodama ask`, `kodama answer`, `kodama done`, or
  `kodama noop`.
- **lane** — an open path or issue on the board. A question blocks one
  lane, not the task.
- **lock** — a `mkdir` lock keyed by `(task, agent name)`. Two runs of
  one agent on one task are excluded; a worker and an auditor run
  together.
- **ledger** — one JSONL file at the root, one line per event. The
  ledger is the operator's truth; the board is the agents' truth.
- **router** — the live probe that picks `(model, thinking)` at spawn,
  ported from the `__wisp_route` zsh function.
- **distill** — the unguarded turn that writes a handoff post when a
  run hits the context guard. A distilled session is closed, not
  continued.

## 1. What round 1 got wrong

| Round 1 | Round 2 | Why |
|---|---|---|
| `.kodama/` with `agents/<type>/agent.toml` | `kodama-sessions/` with an agent as a wisp session template | Owner: "I don't want config files. I want to submit an agent similar to `wisp new`." |
| `needs` and `gives` form a type system | No type system. Free posts, free artifacts, free action | Owner: "I don't want a type system. I want emergent behavior." |
| `writes` scope per agent type | No write scope. One lock per `(task, agent)` | Owner: "`writes` no. ... basically `wisp new` template session folder to copy." |
| One model ladder per agent type | One live probe per spawn; the pair is a spawn decision | Owner: "model+thinking needs to be routed based on live probes, like today's zsh functions do." |
| A question stops the task in `asking` | A question blocks a lane; other lanes keep running; an agent may answer | Owner: "A question can block a small part of the full task. Also, we need a way to run unattended." |
| Guard 75 → `wisp continue` | Guard 75 → one unguarded distill turn, then a fresh spawn | Owner: "The context is drained ... it needs to get a message to distill, similar to how `wispy` has." |
| One `render-past` per run is enough | One ledger index plus `task trace --all` and `--run` | Owner: "With N wisps, one render-past cannot show everything." |
| Five coordination systems, each a substrate | Ten wake rules over one board; the board is the substrate | Owner: "only the blackboard comes close. ... Do another design round. More strategies." |

## 2. Requirements

The round-1 list stands except for the rows marked \*. Full text is
this section; the round-1 wording is superseded.

| # | Level | Requirement |
|---|---|---|
| R1 | MUST | The root process is not an LLM. Zero model tokens outside a run. |
| R2 | MUST | A run is one smol wisp session: guard at most 50%, at most one artifact, at least one post. |
| R3\* | MUST | An agent is a wisp session template. `kodama agent submit` builds the persona and calls `wisp new`. No registry file, no type schema. |
| R4 | MUST | `kodama task submit` takes text on stdin, files by path, an optional acceptance command, and a strategy name. |
| R5\* | MUST | `kodama task await ID` blocks until done, failed, or stuck on an owner question. Exit 0, 1, or 3. `status` is non-blocking; `watch` follows until the task ends. |
| R6 | MUST | `kodama task steer ID` posts a steer note and queues the same text into every live run of the task. |
| R7 | MUST | `kodama task log ID` lists every run and every scheduler event in time order. |
| R8 | MUST | The ledger is append-only and complete. A retry, a model change, a park, and a distill are rows, never silences. |
| R9 | MUST | Scope: every path derives from one `kodama-sessions/` root. Several roots run on one PC without collision. |
| R10 | MUST | The rate limiter is machine-wide. One company server, one bucket, all roots. |
| R11\* | MUST | Recovery covers 429, timeout, crash, guard stop, empty output, failed acceptance, and budget. A guard stop distills; it never continues the drained session. |
| R12\* | MUST | A question blocks a lane, not the task. A peer run or the owner answers. `--unattended` lets a peer answer bind. |
| R13 | SHOULD | The order is not fixed. The strategy can change the wake sequence per task. |
| R14\* | MUST | Every run's full trace stays readable with `wisp render-past`, and the task offers one aggregate view over the ledger. |
| R15 | NEVER | kodama edits an artifact. Only runs write files. |
| R16 | NEVER | kodama hides a retry, a model fallback, or a cost overrun. |
| R17\* | MUST | A spawn copies an agent template and rewrites the model at spawn. The template holds no model decision. |

## 3. The substrate

### 3.1 The tree

```
kodama-sessions/                 # the root; one per project
  board/
    .seq                         # the next post number, under flock
    .lock                        # one flock for seq + post write
    posts/<seq>-<run>.json       # one immutable post per file
  agents/<name>/                 # a wisp session template, never run
    wisp.jsonl                   # the persona as the system record
    wisp.run.json                # the placeholder model
    wisp.usage                   # empty
  tasks/<id>/
    task.md                      # the request, the workdir, the accept
    files/                       # inputs copied at submit
    artifacts/                   # agent-written files, free names
    root/                        # a never-run session; parent of every run
      wisp.jsonl
      wisp.run.json
    runs/<run>/                  # a copy of one agent template
      wisp.jsonl                 # persona + this run's records
      wisp.run.json              # the routed model
      prompt.txt                 # the digest the run read
      wisp.stream                # raw SSE, temporary
      stderr                     # the run's stderr
    state                        # a cache: queued|running|asking|done|failed|cold
    locks/<name>/                # one mkdir lock per (task, agent)
  ledger.jsonl                   # every event, every task
  scheduler.lock/                # one scheduler per root
~/.kodama/
  route.json                     # the last probe verdict, 15 s TTL
  limits/<model>.json            # machine-wide buckets, under flock
```

`task submit` takes text on stdin, copies each `--file` into
`tasks/<id>/files/`, and writes `task.md` with the workdir and the
acceptance command.

The owner's `kodama-sessions/<id>` maps to `tasks/<id>/` for a task and
`agents/<name>/` for an agent. The root is the directory that holds
both. A task is a thread on the root board, not a separate board.

### 3.2 An agent is a session template

`kodama agent submit` builds the persona and calls `wisp new`:

```shell
kodama agent submit --name worker -s ./roles/worker.md \
  --skill testing-without-mocks --skill top-down
# builds: wisp build-system-prompt --wisp --agents-md --skills
#         + the role file + each skill body
# calls: WISP_SESSIONS_ROOT=kodama-sessions/agents \
#        wisp new --name worker -m <probe model> -t <probe thinking> -s persona.txt
```

The template holds the persona in `wisp.jsonl` and a model pair in
`wisp.run.json`. The model pair is a placeholder: every spawn
re-probes and rewrites the pair. The template does not use
`--env-in-system-prompt`, because that block would name a model the
spawn is about to replace. The run prompt names the model instead.

There is no `agent.toml`, no `needs`, no `gives`, no `writes`, no
`max_usd`, and no per-agent ladder. The persona says what the agent is
good at. The board says what is open. The agent decides.

The template is a snapshot of the `AGENTS.md` chain and the skills
catalog at submit time. Re-submit after a persona or skill change.

The run prompt forbids subagents. kodama is the only spawner: a nested
`wisp new --parent` would sit outside the ledger and the locks.

### 3.3 A spawn is a copy

The spawn sequence, one run:

1. Route the model (section 3.7).
2. Take the lock `tasks/<id>/locks/<name>/` (section 3.5).
3. Copy `agents/<name>/` to `tasks/<id>/runs/<run>/`.
4. Rewrite the copy's `wisp.run.json`:
   `{"model": <routed>, "thinking": <routed>, "parent": "tasks/<id>/root"}`.
5. Append `<run>` to `tasks/<id>/root/wisp.run.json` `children`. This
   is best-effort: the write is a read-modify-write of one file, the
   same last-writer-wins race as wisp's `link_child`, so two parallel
   spawns can lose one id. The ledger holds every run path;
   `wisp ls --tree` is a convenience, not the index.
6. Write `runs/<run>/prompt.txt` (section 4).
7. Run:
   `wisp run -d runs/<run> --context-guard 45% < prompt.txt > wisp.stream 2> stderr`.
8. Reap, read `wisp.usage`, `wisp.log`, and the exit code; append the
   ledger rows; release the lock.

Verified on 2026-11-10: a copied template kept its persona, honored a
rewritten `model=routed-model`, and appended the new user prompt. The
test used a closed local URL, so no model was called.

The copy is why the template can stay model-free: `wisp new` fixes the
model, but a copy lets kodama rewrite the pair before the first run.
`wisp continue` cannot change the pair, so a guard-stopped session is
distilled and abandoned, never continued (section 7).

### 3.4 The board protocol

One post is one JSON file:

```json
{"seq": 12, "ts": "2026-11-10T16:20:03Z", "task": "t-0007",
 "run": "r-0004", "agent": "worker", "kind": "note",
 "about": ["artifacts/retry.py"], "next": "tester",
 "text": "Added jitter; local suite passes. Next: run the flaky suite."}
```

Fields:

| Field | Meaning |
|---|---|
| `seq` | The global order. Allocated under `board/.lock`. |
| `task` | The thread. A post may name another task; its writer still holds one lock. |
| `run`, `agent` | The author. |
| `kind` | `task`, `note`, `noop`, `q`, `a`, `done`, `audit`, `distill`, `bid`, `vote`, `steer`, `reject`. |
| `about` | The paths or threads the post concerns. Free text, used by the digest. |
| `blocks` | A `q` post only: the paths that wait on the answer. |
| `q`, `re` | A question id and the question an answer or a vote refers to. |
| `next` | An optional hint, never a command. |
| `text` | The prose. The digest truncates it. |

A run writes posts only through the helper verbs, so quoting is not the
agent's problem:

```shell
kodama post  --kind note --about artifacts/retry.py <<< "..."   # --about repeatable
kodama ask   --blocks artifacts/retry.py <<< "jitter seed in config or env?"
kodama answer q-3 <<< "env; keep the config file absent"
kodama done  --evidence artifacts/retry.py <<< "the suite passes"
kodama noop  --why "nothing open that worker can do"
```

The verbs are the medium, not a role: any agent may post any verb.
Paths in a post are relative to the task dir, and the helpers resolve
them. The run's CWD is the project root; the prompt names
`$KODAMA_TASK_DIR`, so `artifacts/retry.py` never lands in the repo by
accident.

The helpers are kodama, but the run is the author: a helper writes one
board file and one ledger line, and nothing else. R15 holds because a
post is not an artifact. kodama itself writes the prompt, the board
files, the ledger, `accept.log`, and `state`; it never writes under
`tasks/<id>/artifacts/` and never writes `final.md`.

The run environment carries `KODAMA_ROOT`, `KODAMA_TASK`, `KODAMA_RUN`,
`KODAMA_AGENT`, `KODAMA_TASK_DIR`, and kodama's directory on `PATH`.

`task submit` writes the first post of a thread (`kind:task`) with the
request and the workdir. Every later post cites that thread.

Posts are immutable. A correction is a new post that cites the old
`seq`. The board never shrinks; a janitor run may write a digest post,
but it may not delete.

### 3.5 Locks: one per task and agent

`tasks/<id>/locks/<name>/` is a `mkdir` lock. `mkdir` is atomic. The
lock directory holds `owner`:

```json
{"run": "r-0004", "pid": 12345, "ts": "2026-11-10T16:19:00Z"}
```

The scheduler takes the lock before the copy and releases it after the
reap, including on kill and timeout. A second run of the same agent on
the same task waits or is skipped. A different agent runs at once:
`worker` implements while `auditor` reads and `tester` builds a test.
That is the owner's rule.

A stale lock is a lock whose pid is dead or whose age exceeds the run
wall clock plus a grace. The scheduler breaks a stale lock, appends
`stale-lock`, and proceeds. A run never takes a lock itself; the
scheduler owns the lock lifetime. A run that wants other work posts a
`next` hint; a later pick may honor it, and that pick takes its
own lock.

No write scope means the repo is open to a run. The accept command and
the audit are the guard; kodama does not jail the filesystem. The
operator reviews `git diff` in the workdir.

One scheduler per root: `kodama-sessions/scheduler.lock/`. A second
`task run` for the same root fails with a clear line. Many roots run
at once; the only shared file is the machine-wide limiter.

### 3.6 The ledger

`ledger.jsonl` is one line per event, append-only, under `flock`:

```json
{"seq":1,"ts":"...","task":"t-0007","event":"submit","state":"queued"}
{"seq":2,"ts":"...","task":"t-0007","event":"spawn","run":"r-0001","agent":"worker","model":"deepseek-v4.1-flash","thinking":"xhigh","guard":"45%","pid":123}
{"seq":3,"ts":"...","task":"t-0007","event":"post","run":"r-0001","post":12,"kind":"note"}
{"seq":4,"ts":"...","task":"t-0007","event":"run","run":"r-0001","exit":0,"in":8200,"out":400,"usd":0.004}
{"seq":5,"ts":"...","task":"t-0007","event":"question","q":"q-3","blocks":["artifacts/retry.py"],"asker":"worker"}
{"seq":6,"ts":"...","task":"t-0007","event":"answer","q":"q-3","by":"oracle","run":"r-0002"}
{"seq":7,"ts":"...","task":"t-0007","event":"guard","run":"r-0003"}
{"seq":8,"ts":"...","task":"t-0007","event":"distill","run":"r-0003","exit":0,"post":17}
{"seq":9,"ts":"...","task":"t-0007","event":"accept","exit":1,"log":"accept.log"}
{"seq":10,"ts":"...","task":"t-0007","event":"state","state":"running"}
```

The ledger is the only complete history. `task log` projects it to
rows; `task status` reads the tail; `task trace` uses its `run` paths
to render sessions. A restart reads the ledger, finds live pids, reaps
or marks them dead, breaks stale locks, and continues.

### 3.7 The router: live probe at spawn

The router ports `__wisp_route` from the owner's zsh functions. It
fetches `https://litellm.gratex.ai/monitor/api/status` and
`/monitor/api/v1/load`, with an 8 s timeout, and picks:

| Condition | Pair |
|---|---|
| Every `deepseek-v4.1-flash` endpoint is online and no endpoint waits | `deepseek-v4.1-flash`, `xhigh` |
| Any deepseek endpoint is offline, waits, or the probe fails | `glm-5.3`, `high` |

The verdict is cached in `~/.kodama/route.json` for 15 s under
`flock`, so N spawns do not hammer the monitor. A stale or missing
cache means a fresh probe. A probe failure falls back to `glm-5.3
high` with the reason recorded.

Local signals refine the probe: kodama's own in-flight count per model
and the last 20 ledger rows. A model with three recent 429s is parked
for a backoff even when the monitor says free. If both pairs are
parked, the scheduler sleeps one tick and logs `parked`; it starts no
run.

An agent may pin a pair with `kodama agent submit -m ... -t ...`. A
spawn uses the pin when set, else the probe. A percent guard needs a
context window in the model-info file that becomes `wisp.modelcfg`;
the router checks the pair has one before spawn, and fails the spawn with a `no-context` ledger row
otherwise. A token guard is the fallback.

### 3.8 The limiter and the budget

`~/.kodama/limits/<model>.json` is a machine-wide bucket:

```json
{"window": 1780000000, "in": 812340, "out": 40211, "runs": 17,
 "inflight": 2, "cap_in": 2000000, "cap_out": 400000, "cap_runs": 30}
```

The scheduler acquires a slot before spawn and releases it on reap.
Tokens land from `wisp.usage`. The window refills on a fixed clock. All
roots read the same files under `flock`; R10 holds.

The task budget comes from `--max-usd` and the root budget from
`--max-usd` at init. The ledger sums `usd` per run. A missing price
(`<noprice>`) switches the budget to tokens, and the ledger says so.
A spawn whose projected cost (last run of that agent × 1.5) would
exceed the remainder is refused with `budget-stop`. `task await` then
exits 1.

## 4. The wake: one digest, one prompt

### 4.1 The digest

Every run reads a bounded digest, built by kodama from the board and
the artifacts. The digest is code, not a model call; it costs no
tokens beyond the prompt it becomes.

```
<task id="t-0007">
... first 2 KB of task.md ...
</task>

<board>
OPEN TASKS: t-0007 retry (you); t-0008 flaky tests
OPEN QUESTIONS:
  q-3 blocks artifacts/retry.py asks:any age:4m attempts:1
    "jitter seed in config or env?"
DONE PROPOSALS: r-0007 artifacts/retry.py (worker)
ARTIFACTS:
  artifacts/retry.py 4.2k 16:18 "def fetch(..."
RECENT POSTS:
  p-12 worker note about artifacts/retry.py: "Added jitter..."
  p-11 oracle answer q-2: "Use the repo cache."
LOCKS: worker=busy, oracle=free
BUDGET: $0.07 of $1.00
</board>

<you>
You are worker, run r-0009, on deepseek-v4.1-flash (xhigh).
Do one small unit of work on t-0007, or post why you did nothing.
Write at most one artifact under $KODAMA_TASK_DIR/artifacts/ with any
name you choose.
Announce it with `kodama post`.
If a decision blocks you, run `kodama ask --blocks <path>`.
If you believe the task is done, write $KODAMA_TASK_DIR/artifacts/final.md
and run `kodama done`.
</you>
```

Bounds: 2 KB of task text, 40 artifact lines, 8 recent posts at 400
characters each, 6 questions. The whole prompt stays under 12 KB. The
persona adds its own size. A 45% guard of a 128K window leaves room
for the work rounds, which is the point of R2.

The digest filters by the task the scheduler picked, and adds one line
per open task. The agent may notice other work; the scheduler still
holds the lock for the assigned pair. A run that wants to move posts a
`next` hint, and a later pick may honor it under the strategy's rules.

### 4.2 The scheduler loop

```text
while the task is not terminal:
  reap finished runs; append run rows; release locks
  if budget or task clock is spent: state failed; exit 1
  candidates = every unlocked, unparked (task, agent)
  if a slot is free and the limiter allows and candidates:
    pick = strategy(candidates, board, ledger)
    spawn(pick)                      # section 3.3
  if no run is live and no candidate is spawnable:
    if an owner question is open: state asking; await exits 3
    elif the strategy says cold: spawn one close run; stop
    else: append a tick row; sleep
  append a heartbeat row every tick
```

The loop is single-threaded; one `subprocess` per slot, one wall clock
per child. No threads, no daemon, no queue server. A restart re-reads
the ledger and the board and continues.

A tick with no new substantive post (a `note`, `q`, `a`, `done`, or
`distill`; a `noop` does not count), no new artifact mtime, and no
live run increments the idle counter. After `--idle-ticks` (default
5) the task is cold. With an owner question open it goes `asking`; without one it
goes `failed` with `no-progress`. The chorus and field strategies may
spawn one close run at that point, and that run writes a `done` post.

### 4.3 NO-OP is a result

A run that sees nothing useful posts `kind:noop` with one line and
exits. The ledger records it. The scheduler lowers that agent's wake
weight for this task, so the same agent does not burn the next slot.
A run that produces no artifact and no post is an empty-output failure
(section 7), not a NO-OP.

The distinction matters: the swarm must be free to say "not mine"
without lying, or every slot becomes a guess.

## 5. Questions, lanes, and unattended answering

### 5.1 A question is a scoped post

```shell
kodama ask --blocks artifacts/retry.py --asks any <<< "jitter seed in config or env?"
```

The question becomes one post with a `q` id and a `blocks` list. The
digest marks the blocked paths, and a run that would touch one is told
to pick other work or answer. Other lanes keep running.

A lane is not a data structure. A lane is an `about`/`blocks` path. A
question blocks the paths it names and nothing else. The task does not
enter `asking` because one lane waits; the task enters `asking` only
when no spawnable work remains and an owner question is open.

### 5.2 Who answers

| Answer path | Who | When |
|---|---|---|
| Peer answer | Any run, via `kodama answer` | The question is in the digest. No permission needed. |
| Boosted answer | The agent named by `--boost`, picked more often | `--unattended`, after one tick with the question open |
| Owner answer | `kodama task answer ID q-3` | Whenever the owner chooses |
| Escalation | An answerer posts `cannot` twice, or two peers disagree | The question gains `asks:owner`; `await` exits 3 when the task is otherwise stuck |

A peer answer is a normal post. It binds or advises by policy:

| Policy | Behavior |
|---|---|
| `advisory` (default, no `--unattended`) | The owner must answer. The task stays `asking` when stuck. Peer answers are context. |
| `peer` (`--unattended`) | The first answer from an agent different from the asker unblocks the path. A dissent post reopens it. Two attempts without consensus escalate. |
| `owner` | Only `task answer` counts, even under `--unattended`. |

`--unattended` is a task flag. It changes the answer policy to
`peer` and adds a boosted answerer. The scheduler keeps going in both
modes.

The answer budget is part of the task budget. Each question gets at
most `--answers K` peer runs (default 2). A question that spends its
budget escalates; it never loops.

### 5.3 The verbs and the exit codes

```shell
kodama task status ID          # instant: lanes, questions, locks, budget
kodama task await  ID          # block: exit 0 done, 1 failed, 3 stuck
kodama task await  ID --first-question   # exit 3 at the first owner question
kodama task watch  ID          # follow the ledger, one line per event
kodama task answer ID q-3      # the owner's answer
kodama task steer  ID           # a note to the board and to live runs
```

`await` exit 3 means one thing: the task has no progress left without
the owner. That is not the same as "a question exists". The owner can
read `status` while other lanes run, answer early, or wait.

The state file is a cache. `await` recomputes from the ledger when the
cache is older than the last row, so a killed scheduler cannot lie.

### 5.4 Two question traces

Unattended, one lane waits and the others do not:

```text
16:01 r-1 worker  ask q-3 blocks artifacts/retry.py "seed in config or env?"
16:02 r-2 tester  note about tests/test_retry.py "scaffold ready"
16:03 r-3 oracle  answer q-3 "env; keep the config file absent"
16:04 q-3 closed by a peer; artifacts/retry.py is unblocked
      the tester lane never waited
```

Escalation, the peers disagree:

```text
16:01 r-1 worker  ask q-4 blocks artifacts/api.md "v1 or v2?"
16:02 r-2 oracle  answer q-4 "v2"
16:03 r-3 auditor answer q-4 "v1; v2 breaks the client"
16:04 q-4 asks:owner; the task keeps the other lanes
16:05 await exits 3 only when no other lane is open
```

Both traces are board posts and ledger rows. `task status` prints the
same two lines at any moment: the open question with its age and
attempts, and the lanes that did not stop.

## 6. Done: accept, quorum, audit

### 6.1 The acceptance command

`task submit --accept 'pytest -q'` names the proof. A run that believes
the task is done writes `artifacts/final.md` and posts:

```shell
kodama done --evidence artifacts/final.md <<< "suite green on the retry path"
```

The scheduler runs the command after a `done` post exists. It runs
the command once per new `done` post; a second attempt is a new run and
a new ledger row. The command runs in the task workdir (the `workdir:` line of
`task.md`, default the project root), its output lands in
`accept.log`, and the ledger gets one `accept` row.

- Exit 0: state `done`; `final.md` is the answer.
- Exit nonzero: a `reject` post carries the first 2 KB of the log; the
  task stays `running`; the next run sees the rejection. No hidden
  retry: the next attempt is a new run row.

### 6.2 Without an acceptance command

Two `done` posts from two different agents, plus one `audit` run. The
audit reads the task, the evidence, the board, and `git diff` in the
workdir when the task names one, then posts `audit:ok` or
`audit:reject`. The audit is a normal run of any agent
not among the proposers; `--boost auditor` makes the choice likely
without making it mandatory. If every agent is a proposer, the task
fails with `no-auditor` rather than accepting itself.

The quorum is the blackboard rule the owner liked: two strangers agree,
then one stranger checks. In `--unattended` the audit is required; the
owner may still veto.

### 6.3 Who writes final.md

A run writes `final.md`; kodama never does. The closing run writes it
from the board's accepted evidence, or a `done` post names an existing
artifact as the deliverable. `task await` prints the deliverable path
and, on exit 0, its first 40 lines.

## 7. Recovery

### 7.1 The matrix

| Failure | Detection | Action |
|---|---|---|
| 429 | `wisp.log` `http_error ... err=429`, or stderr | Park the model for a backoff; ledger `park`; retry with a fresh copy; no silent retry |
| Timeout | kodama's wall clock | SIGTERM (wisp commits the tail), then SIGKILL; ledger `killed`; resume only if the tail is open |
| Crash | nonzero exit, no guard | Ledger `crash`; retry with the same session if the tail is open, else a fresh copy |
| Guard 75 | exit 75 | One unguarded distill turn; ledger `guard` and `distill`; the session closes |
| Empty output | wisp's 3 degenerate attempts exhausted; exit 1 | Ledger `empty`; one fresh copy with a nudge; then park |
| Failed accept | accept exit nonzero | `reject` post with the log; reopen; ledger `accept` |
| Budget | ledger sum over cap | Ledger `budget-stop`; state failed; `await` exits 1 |
| Stale lock | dead pid or old `owner` | Break it; ledger `stale-lock`; continue |
| Scheduler crash | heartbeat older than three ticks | `task await` exits 1 with `scheduler-dead`; `task run` restarts from the ledger |

Every retry is a row with `retry_of`, `attempt`, and the reason. R16
holds.

### 7.2 The guard distill

A guard stop means the context is full. `wisp continue` at the limit
fails on the first round, which is the owner's objection to round 1.
The fix copies wispy: one turn with no guard, in the same session,
whose only job is to write a handoff.

```shell
# after exit 75, no --context-guard
wisp run -d runs/<run> < distill.prompt
```

The distill prompt is small and fixed:

```
Your context is at the guard. Stop working.
Write one post with `kodama post --kind distill --about <paths>`:
1. what you finished, with exact file names
2. what is left, in one or two steps
3. the exact next action for the next run
4. what you learned that the board does not already say
Write nothing else. Do not continue the task.
```

The run writes a `distill` post. kodama marks the session
`closed:guard` and never continues it. The next spawn of any agent
reads the distill post in its digest and starts near-empty. The guard
is at most 50%, so the session still has about half its window for the
distill turn; that is why the unguarded turn fits.

If the distill fails (provider context error, empty output), kodama
writes `distill-failed` and does not invent a handoff. A later run may
read the stopped session with `wisp render-past` through `task trace
--run`, and the ledger points at it. No silent recovery.

### 7.3 Resume or restart

`wisp continue` works only when the tail of `wisp.jsonl` is a `user`
or `tool` record. kodama checks the tail before choosing:

- tail `user` or `tool`: `wisp continue` with the same guard.
- tail `system` or a finished assistant: a fresh copy; the old session
  is evidence, not a continuation.
- tail unknown or broken: a fresh copy, and the ledger says `restart`.

This rule is why a crash mid-round can resume and a completed turn
cannot. It is also why a guard stop distills instead of continuing:
the tail is committed, but the context is drained.

## 8. Traces: one index, many sessions

### 8.1 The index

`task log` is the index: one row per run and per scheduler event, from
the ledger. It holds the run id, agent, model, start, exit, tokens,
cost, posts, and session path. The session path is the key: no
children-list lookup is needed.

```shell
$ kodama task log t-0007
16:01 r-0001 worker  deepseek xhigh  ok     in 8.2k out 0.4k $0.004  note
16:02 r-0002 tester  deepseek high   ok     in 9.1k out 0.6k $0.005  note
16:03 r-0003 oracle  glm      high   ok     in 4.0k out 0.3k $0.003  answer q-3
16:05 r-0004 worker  deepseek xhigh  guard   in 64k  out 2.1k $0.020  distill
16:06 r-0005 worker  glm      high   ok     in 6.0k out 0.8k $0.004  note
```

### 8.2 The aggregate

```shell
kodama task trace t-0007            # the summary table, same as log
kodama task trace t-0007 --all      # the merged view: every run, banners between sessions
kodama task trace t-0007 --run r-0004  # one session dir, for wisp render-past
kodama task trace t-0007 --grep 429 # matching records across the task's runs
kodama task trace t-0007 --since 16:03
```

`--all` calls `wisp render-past -d <run>` for each ledger-listed run and
prints a banner before each:

```
### run r-0004 worker deepseek-v4.1-flash xhigh 16:05 exit 75 (guard)
[think] ...
[answer] ...
```

`--run` prints the session dir alone, so `wisp render-past -d "$(...)"`
works. `--grep` reads each run's `wisp.jsonl` and `wisp.log` and prints
matching lines; it does not rely on `wisp grep --tree`, because the
children list can lose an id under parallel spawns.

### 8.3 Live

`task watch` follows the ledger: one line per spawn, post, question,
answer, guard, accept. It is the live overview. `wisp render-live` on
one run is the deep live view; `task trace --run` names the dir.

The split is deliberate: the ledger is the swarm's heartbeat; one
session is a single conversation. Following N raw streams at once is
unreadable, and the owner asked for one view, not a firehose.

## 9. Strategies: ten wake rules over one board

A strategy is one `pick(candidates, board, ledger)` function. The
substrate does not change: the same board, the same templates, the
same locks, the same questions, the same recovery, the same traces.
A strategy changes only which `(task, agent)` pair the next free slot
gets. Each is 30 to 80 lines.

The round-1 systems survive as degraded wake rules:

| Round 1 | Round 2 | What changed |
|---|---|---|
| conveyor | queue | No `needs` graph. The board's oldest open thread is the queue. |
| blackboard | bulletin, ranked | No artifact claims. One lock per `(task, agent)`. Votes are optional. |
| handoff | relay | `next` is a hint, not a command. |
| epochs | chorus | Parallel clones on a flagged decision, not a barrier per epoch. |
| stigmergy | field | The score is per thread, not per agent type. |
| — | auction, bounty, gossip, clonal | Four new signals: bids, price, sampling, population. |

The ten signals are distinct: none, peers, self-report, price, local
knowledge, a field, a sample, history, parallelism, age. No two
strategies read the same signal.

### 9.1 Bulletin (default)

**Signal:** none; idleness and age.
**Pick:** uniform over unlocked `(task, agent)`, weighted by the ticks
since that agent last ran on that task and by the task's age.
`--boost NAME` multiplies one agent.
**Done:** the acceptance command, else two different agents' `done`
posts plus one audit.
**Questions:** every digest carries the open questions; any run may
answer. After `--answers` attempts without consensus, escalate.
**First principles:** a shared log is the cheapest coordination
medium; random wake explores role assignments no plan names; idle
weighting starves nobody; a NO-OP must be cheap.
**Failure:** wasted wakes and board rot. Mitigation: NO-OP weight
decay, one digest post from a janitor run, `--max-idle`.
**Use:** the default; the colleague's board.

### 9.2 Ranked board

**Signal:** votes.
**Pick:** score each open thread by `vote` posts, one per run, `+1` or
`-1`, weighted by recency and by voter independence (a different agent
counts more). Spawn the agent named in the top thread's `next`, else
the top voter.
**Done:** the top-ranked `done` proposal passes the accept or quorum.
**Questions:** a voted question rises; its top voter is spawned first.
**First principles:** many weak signals become one order without a
planner; a vote is one post; popularity is not correctness, so decay
and independence weights are mandatory.
**Failure:** rich-get-richer and a wrong top thread. Mitigation: an
`--explore` fraction of random picks.
**Use:** many open threads, unclear priority.

### 9.3 Auction (contract net)

**Signal:** bids.
**Pick:** a post may carry `kind:bid` with `item`, `tokens`, and
`confidence`. The scheduler awards the best `confidence / tokens` bid
and spawns that agent on that item. For large tasks, a dedicated bid
round spawns two or three agents with a bid-only prompt.
**Done:** the awarded run's accept or quorum.
**Questions:** a question is an item; an answer is a bid target.
**First principles:** the worker knows the cost better than the
scheduler; a bid is a promise the ledger can check; separate bid
rounds cost as much as the work, so embed bids in ordinary posts by
default.
**Failure:** optimistic bids and noisy estimates. Mitigation: an EWMA
of bids versus actuals per agent.
**Use:** heterogeneous work, expensive runs, many agents.

### 9.4 Bounty market

**Signal:** price.
**Pick:** each thread or question carries a bounty in USD or tokens,
set at submit or raised by a doubt (`kodama bounty q-3 +100k`). The
scheduler spawns the agent with the best bounty over estimate; the
ledger records the award to that agent when the post lands.
**Done:** the total bounty is spent, or accept/quorum.
**Questions:** an unanswered question's bounty rises with age; that is
the escalation clock.
**First principles:** scarcity allocates attention without a plan; the
budget is the one resource kodama already meters; a market needs a
price, and a wrong price starves important work.
**Failure:** price setting becomes a planner in disguise. Mitigation:
treat bounties as hints and keep an explore fraction.
**Use:** a root board with many tasks; attention is scarce.

### 9.5 Relay (handoff, weakened)

**Signal:** the last post's `next` hint.
**Pick:** follow the latest `next` with probability `p` (default 0.5)
when that agent exists and is unlocked; otherwise fall back to
bulletin. A `next` is never binding.
**Done:** accept, else quorum plus audit.
**Questions:** an agent writes `next: user` or asks; the question
system handles it.
**First principles:** the finishing agent holds local knowledge the
scheduler lacks; a hint is cheap and ignorable; a binding next is a
plan, a hint keeps emergence.
**Failure:** herding and lost novelty. Mitigation: `p < 1` and a
random fallback.
**Use:** deep single-thread work with a natural next step.

### 9.6 Stigmergy field

**Signal:** a score per thread.
**Pick:** score = open doubts + unanswered questions + recent
citations − age. Spawn the agent named by the top thread. Decay every
tick.
**Done:** cold. When the maximum score stays below `epsilon` for `K`
ticks, one close run writes `final.md` and triggers the accept.
**Questions:** a question raises its thread's score; an answer lowers
it.
**First principles:** a field aggregates local judgments without an
author; decay is a stop rule nobody can lie about; the weights are the
policy, so expose them.
**Failure:** oscillation and tuning. Mitigation: `kodama score
--explain` and a damping term.
**Use:** open-ended sweeps where no one knows the last step.

### 9.7 Gossip

**Signal:** a random sample of the board.
**Pick:** each run reads two random recent posts and one random old
post, not the full digest; the run posts a merge, an answer, or a
NO-OP. The scheduler is bulletin.
**Done:** `K` independent mentions of the same claim, plus accept or
quorum.
**Questions:** a question spreads by mention; `K` mentions escalate.
**First principles:** sampling bounds the context per run; repeated
mention is evidence; no complete view means dead ends persist, so
anti-entropy needs a periodic full-board run.
**Failure:** slow convergence and duplication. Mitigation: a fanout
cap and a periodic `librarian` full read.
**Use:** many agents, a large board, cheap runs.

### 9.8 Clonal (ecology)

**Signal:** population weights.
**Pick:** each agent has a spawn weight. A post that cites its artifact
raises the weight; a NO-OP or a dissent lowers it; the weight decays
to a floor. Pick weighted.
**Done:** accept or quorum.
**Questions:** an answer that closes a question raises the answerer's
weight.
**First principles:** useful agents reproduce and useless ones go
dormant; the swarm adapts without a plan; runaway cloning is the
failure, so cap the weight and the consecutive clones.
**Failure:** monoculture; a lucky agent crowds out a needed one.
Mitigation: a weight floor and a novelty bonus.
**Use:** a large roster and an unknown task shape.

### 9.9 Chorus (epochs, weakened)

**Signal:** a flagged decision.
**Pick:** a post may flag `decision`; the scheduler spawns `N` agents
on that item in parallel, with different personas or model pairs; one
merge run consolidates. Ordinary work has no barrier.
**Done:** the merge's accept or quorum.
**Questions:** the chorus votes on a decision question; the merge
writes the answer.
**First principles:** diversity comes from personas and models, since
wisp has no temperature; parallel candidates beat a chain on
decisions; `N` runs cost `N` times, so use the rule only on flagged
decisions.
**Failure:** cost and merge quality. Mitigation: `--chorus 3` and a
merge prompt.
**Use:** architecture choices and ambiguous specs.

### 9.10 Queue (conveyor, weakened)

**Signal:** age.
**Pick:** the oldest open thread on the oldest task. Spawn the agent
named by the thread's `next`, else the least-recently-run unlocked
agent. FIFO.
**Done:** the queue drains, then accept or quorum.
**Questions:** a question holds its own thread, not the queue.
**First principles:** oldest-first guarantees progress and bounds
starvation; the agents' posts write the queue; a queue cannot reorder
for value.
**Failure:** head-of-line blocking. Mitigation: `--queue-skip` for a
blocked thread.
**Use:** a known backlog and a predictable drain.

### 9.11 Comparison

| | Signal | Next pick | Coord. tokens | Parallel | Reproducible | Stop rule | Main risk |
|---|---|---|---|---|---|---|---|
| Bulletin | none | weighted random | 0 | yes | no | accept / quorum | wasted wakes |
| Ranked | votes | top thread | 1 vote/run | yes | no | accept / quorum | popularity |
| Auction | bids | best bid | 1 bid/run | yes | no | accept / quorum | optimistic bids |
| Bounty | price | best ratio | 0 | yes | no | spent / accept | wrong price |
| Relay | `next` | hint, p | 0 | partly | no | accept / quorum | herding |
| Field | score | top score | 0 | yes | no | cold | oscillation |
| Gossip | sample | random | 0 | yes | no | K mentions | slow |
| Clonal | weights | weighted | 0 | yes | no | accept / quorum | monoculture |
| Chorus | flag | N clones | 0 | yes | mostly | merge + accept | cost |
| Queue | age | oldest | 0 | yes | yes | drain + accept | head-of-line |

## 10. Defaults and build order

Defaults:

| Knob | Default |
|---|---|
| Strategy | `bulletin` |
| Slots | 2 |
| Guard | 45% |
| Tick | 2 s |
| Run wall clock | 10 min |
| Task wall clock | 2 h |
| Route | the live probe, 15 s cache |
| Answer policy | `advisory`; `peer` under `--unattended` |
| Answers per question | 2 |
| Retries per run | 2 |
| Trace | on demand |

Build order:

1. Substrate: root, `agent submit`, `task submit`, spawn copy, board
   helpers, locks, ledger, router, limiter.
2. Digest and the bulletin scheduler.
3. Questions, lanes, peer answer, escalation.
4. Done: accept, quorum, audit.
5. Guard distill and the recovery matrix.
6. `task log`, `task trace`, `task status`, `task watch`.
7. The other strategies, one at a time: ranked, relay, auction,
   bounty, field, gossip, clonal, chorus, queue.

The first slice is a single task, the bulletin scheduler, one agent,
the accept command, and `task log`. No questions, no distill, no
strategy menu. That slice proves the copy-spawn, the board, the lock,
and the ledger. Everything else is additive over the same substrate.

## 11. Open questions for the owner

| # | Question | Options | Rec |
|---|---|---|---|
| Q1 | Is `accept` mandatory? | (a) mandatory; (b) optional, quorum + audit; (c) optional, quorum only | b |
| Q2 | Which strategy is the default? | (a) bulletin; (b) ranked; (c) queue | a |
| Q3 | Does a peer answer bind? | (a) advisory by default, peer under `--unattended`; (b) always advisory; (c) always binding | a |
| Q4 | Is the board per root or per task? | (a) one root board, tasks are threads; (b) one board per task | a |
| Q5 | Is a merged trace stored or on demand? | (a) on demand; (b) a stored `trace.log` per task | a |
