Superseded by `design-options-2.md` (round 2, 2026-11-10).

# kodama — goals, requirements, five coordination systems

Status: design for review. No code.

`kodama` runs a loosely coordinated swarm of short wisp sessions.
Loosely coordinated means: no agent holds the plan. Each agent sees the
artifacts and its own small job.

## 0. Terms

- **kodama** — the root script. Not an LLM. Spawns runs, enforces limits, writes the ledger.
- **agent type** — a registered preset: one persona file, one model ladder, one small guard, one artifact.
- **run** — one short-lived wisp session started by kodama.
- **task** — one submitted request with a folder, runs, and an optional acceptance command.
- **policy** — the rule that picks the next run. The five systems differ mainly in policy.
- **artifact** — a file an agent type produces. Artifacts are the only way information moves.
- **ledger** — one append-only JSONL line per run. The observability layer.

## 1. Goal

Run a swarm of small wisp sessions over one task from one CLI command.
Let the order of runs emerge. Keep the swarm observable, steerable, and
recoverable.

## 2. Requirements

| # | Level | Requirement |
|---|---|---|
| R1 | MUST | The root process is not an LLM. Zero model tokens outside a run. |
| R2 | MUST | A run is one smol wisp session: guard at most 50%, one artifact, one unit. |
| R3 | MUST | Agent types are data. `kodama agent add` writes a registry entry. No code change. |
| R4 | MUST | `kodama task submit` takes text on stdin, files by path, and an acceptance command. |
| R5 | MUST | `kodama task await ID` blocks until done, failed, or asking. Exit 0, 1, or 3. |
| R6 | MUST | `kodama task steer ID` adds information to a live run or the next run of that task. |
| R7 | MUST | `kodama task log ID` lists every run in time order with type, model, tokens, cost, exit, artifact. |
| R8 | MUST | The ledger is append-only and complete. A retry is a row, never a silence. |
| R9 | MUST | Scope: every path derives from one root. Several roots run on one PC without collision. |
| R10 | MUST | The rate limiter is machine-wide. One company server, one bucket, all roots. |
| R11 | MUST | Recovery covers 429, timeout, crash, guard stop, empty output, failed acceptance, budget. |
| R12 | MUST | A user question stops the task in state `asking`. One command answers the question. |
| R13 | SHOULD | The order is not fixed. The policy can change the sequence per task. |
| R14 | SHOULD | A run's full trace stays readable with `wisp render-past` after the task ends. |
| R15 | NEVER | kodama edits an artifact. Only runs write files. |
| R16 | NEVER | kodama hides a retry, a model fallback, or a cost overrun. |

Non-goals: several hosts, a web UI, a memory store, temperature control,
a replacement for wisp.

### Facts inherited from wisp

1. `wisp new` fixes model and system prompt. An agent type is a session-creation decision.
2. `wisp run` has no retry, no wall clock, no cost meter. kodama owns retries, kills, budget.
3. `wisp steer` already queues a message into a live run and into the next run. Steering is nearly free.
4. `wisp new --parent` links a session. `wisp ls --tree` then gives the trace tree for free.
5. A finished round commits to `wisp.jsonl`. The ledger reads wisp's own records. kodama copies nothing.
6. `wisp run` exits 75 on the context guard and stays resumable. Exit 75 is not a failure.
7. Percent guards fail at start when `wisp.modelcfg` holds no context window. `kodama doctor` checks.

## 3. The shared substrate

One floor under all five systems. The floor is most of the code.

```
.kodama/                     # the root: --root, $KODAMA_ROOT, else $PWD/.kodama
  kodama.json                # slots, budget, default policy, limit settings
  agents/<type>/agent.toml   # registry entry
  agents/<type>/persona.md   # system prompt
  tasks/<id>/root/           # a never-run wisp session; --parent of every run
  tasks/<id>/Task.md         # the request, verbatim
  tasks/<id>/accept.sh       # optional; exit 0 means done
  tasks/<id>/artifacts/      # what agents produce
  tasks/<id>/space/          # notes, claims, verdicts, traces (policy-specific)
  tasks/<id>/ledger.jsonl    # one line per run
  tasks/<id>/state           # queued|running|asking|done|failed|cold
  tasks/<id>/question.md     # present only while state=asking
  tasks/<id>/final.md        # the answer
  tasks/<id>/steer.inbox     # steer lines; drained by the policy
~/.kodama/limits/            # machine-wide token buckets and in-flight counters
```

Registry entry:

```toml
name     = "spec"
persona  = "persona.md"
model    = ["DeepSeek V4.1 Flash", "GLM 5.3"]  # ladder: first rung not rate limited
thinking = "high"
guard    = "40%"
needs    = ["designs.md"]     # eligible only when these exist
gives    = ["spec.md"]        # exactly one artifact
writes   = ["artifacts/"]     # the only paths the run may touch
max_usd  = 0.02
```

`needs` and `gives` form the type system. Every policy reads the type
system differently. No policy invents its own.

kodama ships four builtin types, because every policy needs them:
`verify` (write one verdict for one artifact), `audit` (re-read a
final.md against the request), `salvage` (one last attempt with the
failure text in the prompt), and `close` (write final.md from the best
artifacts). The owner's agent ideas are ordinary types:

| type | needs | gives |
|---|---|---|
| frame | — | frame.md |
| meta | frame.md | why.md |
| split | frame.md | units.md |
| adversarial | any artifact | doubt-<name>.md |
| design | frame.md | designs.md |
| spec | designs.md | spec.md |
| worker | spec.md | patch.diff |

Ledger line:

```json
{"t":"15:05:02","run":7,"type":"spec","model":"M","thinking":"high","exit":0,
 "tok_in":9120,"tok_out":1103,"usd":0.006,"session":"runs/07-spec",
 "artifact":"spec.md","note":"retry 1 of 429"}
```

CLI surface:

```
kodama init [--root D]
kodama agent add NAME --persona F -m M[,M2] [-t T] [--guard P]
                        [--needs A,B] [--gives C] [--writes D] [--max-usd U]
kodama agent ls | rm NAME
kodama task submit [--policy P] [--accept CMD] [--budget U] [--attach F] < request
kodama task await ID [--timeout S] [--json]
kodama task steer ID < message
kodama task log ID [--run N] [--follow] [--letters]
kodama task show ID
kodama ls
kodama doctor
kodama stop [--drain]
```

Recovery:

| Signal | Detection | Action |
|---|---|---|
| 429 or quota text | exit 1 plus stderr match | park until the bucket refills, jitter, retry the same rung |
| 3 x 429 on one rung | ledger count | drop the rung, retry on rung 2 |
| guard stop | exit 75 | `wisp continue` once, then re-run with a smaller unit |
| hang | wall clock per run | SIGTERM, then SIGKILL; the ledger row says killed |
| empty output | no artifact, no note | retry once with a stricter prompt, then the `salvage` type |
| accept fails twice | accept exit not 0 | state `failed`; final.md holds the artifact and the failure |
| budget spent | running sum | start nothing new, finish in flight, state `failed` |

Steering: `kodama task steer` writes one line to `steer.inbox`. A
running policy forwards the line with `wisp steer -d <run>`. An idle
task reads the inbox before the next run. While state is `asking`, the
same command also writes the answer. One command, two effects, no
separate answer verb.

Observability, three levels, no duplication:

- `kodama task log` — the ledger, one line per run.
- `kodama task log --run 7` — prints the session dir; `wisp render-past -d` shows every turn.
- `wisp ls --tree -d .kodama/tasks/t-0007/root` — the run tree, free from `--parent`.

## 4. The map: four questions, five answers

| Question | Conveyor | Blackboard | Handoff | Epochs | Stigmergy |
|---|---|---|---|---|---|
| Who picks the next run | a rule table | the agent, when the dice wake the agent | the finishing agent | the epoch counter | nobody; a score field |
| How runs talk | artifacts only | notes on a shared board | one addressed letter | one broadcast note | traces that move scores |
| Who says done | the last stage's exit code | a quorum of two strangers | the author, then one stranger audits | the fold's rubric | decay; the task goes cold |
| How a question surfaces | a stage writes `question.md` and stops | a pinned note, escalated after two rounds | the last letter addresses `user` | the fold ranks open questions | an `ask` action outbids the rest |
| Coordination cost | zero tokens | one board read per run | one note per hop | one fold per epoch | one score pass per tick |
| Main risk | rigid | wasted runs, stale notes | tunnel vision | the slowest run sets the pace | bad weights, oscillation |

## 5. System 1 — the conveyor

Metaphor: an assembly line. The stations live in the rule table.

Next run: kodama lists `artifacts/`, finds every type whose `needs`
exist and whose `gives` is missing, and starts the first one in stage
order. Stage order comes from `--stages` or the policy default. The
needs graph is the schedule.

Done: the stage named `accept` runs `accept.sh`. Exit 0 writes
`final.md` and state `done`.

Messages: none. An artifact is a message everyone can read and nobody
addresses.

Questions: a stage that cannot proceed writes `question.md`, produces
no artifact, and exits 0. The state becomes `asking`. `kodama task
steer` writes `space/answers.md`, and the next tick re-runs that stage.

```shell
kodama init
kodama agent add frame  --persona ./p/frame.md  -m M1 --guard 30% --gives frame.md
kodama agent add attack --persona ./p/attack.md -m M2 --guard 30% --needs frame.md --gives frame.critique.md
kodama agent add design  --persona ./p/design.md -m M1 --guard 40% --needs frame.critique.md --gives designs.md
kodama agent add spec   --persona ./p/spec.md   -m M1 --guard 40% --needs designs.md --gives spec.md
kodama agent add worker --persona ./p/worker.md -m M1 --guard 50% --needs spec.md --gives patch.diff
kodama task submit --policy conveyor --accept 'git apply --check patch.diff' \
  <<< "add retry with jitter to fetch"

$ kodama task log t-0007
15:01 1 frame  ok   8.2k/0.4k   $0.004  -> frame.md
15:02 2 attack ok   9.1k/0.6k   $0.005  -> frame.critique.md
15:03 3 design ok  12.0k/1.9k   $0.007  -> designs.md
15:04 4 spec   ok  10.2k/1.1k   $0.006  -> spec.md
15:05 5 worker ret 429, parked 40s
15:06 5 worker ok  21.8k/2.4k   $0.011  -> patch.diff
15:07 6 accept ok  exit 0                -> final.md

$ kodama task await t-0007 | head -2
done t-0007  6 runs  1 retry  $0.033
```

First principles:

1. A rule table is the cheapest coordinator. A rule table spends no tokens, never drifts, and replays exactly.
2. The rule table makes coordination a data problem. A new order is a new stage list.
3. Rigidity is the price. Every branch needs a rule, and a rule for a branch needs another branch.
4. The conveyor breaks when the work does not fit the artifact set. A rule table cannot notice what nobody named.

## 6. System 2 — the blackboard

Metaphor: a workshop wall with notes pinned on it. Anyone may pin a
note, and anyone may take one down.

Next run: nobody decides. kodama keeps the slots full by starting a
random registered type, weighted by how long the type has sat idle.
Each agent reads `space/board.md` and `artifacts/`, then decides
whether the agent has work. An agent with no work prints `NO-OP` and
exits after one cheap round.

Claiming: an agent claims work with `mkdir space/claims/<artifact>.lock`.
`mkdir` is atomic. A second claimant fails and picks other work.

Done: a quorum. Every contribution needs two `verdicts/<artifact>.md`
files, each from a run of a different model. Two `ok` verdicts accept
the artifact. One `reject` returns the artifact to the board as an
open need.

Messages: yes. A note is a line in `space/board.md`, written once and
read by everyone. Addressing is optional (`@attack: designs.md is
thin`). Notes are the only shared memory.

Questions: an agent that finds an unanswerable contradiction pins a `?`
note and stops. Any other agent may answer. Two rounds without an
answer lift the note to `question.md` and state `asking`.

```shell
kodama task submit --policy blackboard --slots 4 <<< "nightly build got slower this week"

$ kodama task log t-0009 --follow
15:01 1 frame   NO-OP (no open need for frame.md)
15:01 2 design  claim designs.md -> three options
15:02 3 worker  NO-OP
15:03 4 attack  claim critique: designs.md is optimistic
15:04 5 worker  claim patch: instrument the stages
15:05 6 verify  verdict designs.md ok (1/2)
15:06 7 verify  verdict patch ok (1/2)
15:06 8 verify  verdict patch ok (2/2) -> accepted
15:07 9 frame   NO-OP
```

First principles:

1. Random dispatch is free exploration. A random order finds orders a rule table never names.
2. Claims must be atomic. Atomicity stops two agents doing one job; `mkdir` costs nothing.
3. The price is wasted runs. Every NO-OP is a full session with a prompt and a board read.
4. The blackboard breaks when the board rots. Stale notes mislead the reader, so the board needs a janitor type or a TTL.

## 7. System 3 — the handoff chain

Metaphor: a bucket brigade. Each runner turns and names the next
runner.

Next run: the finishing agent. The last output holds one fenced block:

```json
{"next": "worker", "why": "spec.md is ready", "note": "keep the jitter seed configurable"}
```

kodama validates `next` against the registry and `--allowed-next`, then
starts that type with the note as the first line of the prompt. The
root holds no policy, only a legality check and a hop cap.

Done: the author declares `"next": "done"` and writes `final.md`. One
`audit` run then re-reads `final.md` against the request and
`accept.sh`. Two hands: one declaration, one check.

Messages: yes, addressed letters. One letter per hop, with a reason and
a hint. A letter is the cheapest transfer of context.

Questions: an agent writes `"next": "user"`. The state becomes
`asking`, and `await` prints the letter. `steer` writes the reply and
re-enters at that hop.

```shell
kodama task submit --policy handoff --start frame --max-hops 12 <<< "make the CLI usable offline"

$ kodama task log t-0010 --letters
15:01 1 frame  -> attack  "offline breaks the recipe fetch"
15:02 2 attack -> design  "the cache is the real decision"
15:03 3 design -> user    "cache in the repo or in ~/.cache?"
15:03 state: asking
$ kodama task steer t-0010 <<< "in the repo, .wisp/cache"
15:04 3 design -> spec    "repo cache, versioned by model id"
15:05 4 spec   -> worker
15:06 5 worker -> audit
15:07 6 audit  done, accept.sh exit 0
```

First principles:

1. The agent that just worked holds the most context. That agent is the cheapest router for the next hop.
2. One letter per hop keeps each context small. A hop reads one note, not the whole history.
3. The chain has no breadth. A bad hop costs every later hop, and a chain cannot explore two designs at once.
4. The handoff breaks when the model picks an interesting type over a useful type. `--allowed-next` is the guard rail.

## 8. System 4 — epochs

Metaphor: a research team. Everyone works in parallel, the team meets,
the next round starts.

Next run: the epoch counter plus one fold. All eligible types run in
parallel inside an epoch. A barrier waits for every run. One `fold` run
reads the artifacts, writes `space/epoch-N.md`, and names the next
epoch's types.

Done: the fold. The fold writes a rubric score and `stop: true` when
the goal is met. A fold stop is a judgment, not a proof, so
`accept.sh` runs after the fold.

Messages: broadcast. The fold writes one note. Every next-epoch agent
reads that note. No addressing, no side channels.

Questions: the fold collects contradictions across the epoch and ranks
them. `await` prints the top one. `steer` writes the answer as a note
for epoch N+1.

```shell
kodama task submit --policy epochs --epochs 3 --parallel 4 --accept ./bench.sh <<< "pick a queue backend"

$ kodama task log t-0011
e1 15:01 4 runs parallel  design.a design.b design.c attack
e1 15:06 fold            two candidates survive -> epoch-1.md  score 0.4 stop no
e2 15:06 3 runs parallel  attack bench spec
e2 15:14 fold            one candidate survives -> epoch-2.md  score 0.7 stop no
e3 15:14 2 runs parallel  worker attack
e3 15:22 fold            stop true -> final.md                score 0.9
   15:23 accept          exit 0
```

First principles:

1. A barrier trades wall clock for a clean audit trail. Each epoch is one comparable slice.
2. Parallel candidates remove the tunnel vision of a chain. wisp has no temperature, so diversity comes from models and prompts.
3. The slowest run sets the pace. One long run wastes the epoch's slack.
4. Epochs break on strictly sequential work. A barrier around sequential steps is pure waiting.

## 9. System 5 — stigmergy

Metaphor: an ant colony. No ant carries the plan. Ants leave a scent,
and the scent moves the next ant.

Next run: nobody. kodama holds one score per (task, type) pair. A score
rises when the type's `needs` exist and the type's `gives` is missing,
and rises further when a trace doubts the artifact. A score falls with
every run of that type and with age. When a slot frees, kodama starts
the highest score above `epsilon`. Coordination is a hill climb on
"what is most useful now".

Done: decay. When no pair scores above `epsilon` for K ticks, the field
is cold. One `close` pass writes `final.md` from the best artifacts and
runs `accept.sh`. Nothing claims done. The task stops being
interesting.

Messages: traces, not letters. Every run appends a line to
`space/traces.jsonl`:

```json
{"run":4,"writes":["designs.md"],"doubts":["designs.md: no rollback story"]}
```

A doubt raises the score of every type that could address the doubt. A
trace is a message with no addressee.

Questions: `ask` is a type like any other. The `ask` score rises when
the traces hold a contradiction that no artifact resolves. `ask` writes
`question.md`. The user's answer arrives as a trace, and the score
falls.

```shell
kodama task submit --policy stigmergy --epsilon 0.2 --cold-ticks 5 <<< "cut flaky tests by half"

$ kodama task log t-0012
15:01 pick spec      0.91
15:03 trace +spec.md
15:03 scores spec 0.10  worker 0.88  attack 0.55
15:04 pick worker    0.88
15:06 trace +patch.diff  -spec.md:no-rollback
15:06 scores attack 0.79  worker 0.20
15:08 pick attack    0.79
15:10 trace +attack.md:three flaky sources
15:10 scores worker 0.74  ask 0.30
15:12 pick worker    0.74
...
15:31 tick 40: max 0.11 < 0.20 -> cold
15:31 close: accept.sh exit 0 -> final.md

$ kodama task await t-0012
cold t-0012  22 runs  $0.21  final.md written
```

First principles:

1. A score field is a message board without an author. The field holds no plan, only current pressure.
2. Decay is the stop rule. A stop rule nobody declares is a stop rule that cannot lie.
3. The risk is oscillation. Two types that undo each other both score high forever. Doubts must raise scores, and file age must not.
4. Stigmergy breaks when the weights are wrong. The weights are the whole policy, so they need `kodama score --explain`.

## 10. Comparison

| | Conveyor | Blackboard | Handoff | Epochs | Stigmergy |
|---|---|---|---|---|---|
| Order of runs | fixed by needs | random | chosen by agents | batched | emergent from scores |
| Coordination tokens | 0 | one board read per run | one note per hop | one fold per epoch | 0 |
| Reproducible | yes | no | no | mostly | no |
| Parallel | independent stages only | yes | no | yes | yes |
| Audit trail | a straight list | a pile of notes | a chain of letters | comparable slices | a score history |
| Stop rule | exit code | quorum | declaration plus audit | rubric | decay |
| Cost of a wrong turn | one stage | one run | every later hop | one epoch | one run |
| Good for | known pipelines | exploration | deep single-thread work | decisions among candidates | open-ended sweeps |

## 11. Proposed defaults

| Question | Proposal |
|---|---|
| How to coordinate | Policy per task, chosen at submit. Default `conveyor`. |
| Does messaging exist | Yes, as files. Only `handoff` addresses a message. Others share space or leave traces. |
| Who claims done | The acceptance exit code when a command exists. Otherwise one `audit` stranger. |
| How questions surface | `question.md` plus state `asking`; `await` prints, `steer` answers. |
| Where the answer lands | `tasks/<id>/final.md`; `await` prints the file and exits 0. |
| Model choice | One ladder per type; the first rung that is not rate limited. |

Build order: substrate (init, agent add, submit, await, ledger, limits),
then conveyor, handoff, epochs, blackboard, stigmergy. Each policy is
60 to 150 lines over the same substrate.

## 12. Open questions for the owner

1. Root location: `.kodama/` at the repo root, or `~/.kodama/roots/<hash>`? A repo root puts the board next to the code, and two kodamas in one repo collide.
2. What isolation does a task get: a git worktree, a write scope, or nothing? Two workers on one file race.
3. Is `accept.sh` mandatory? A mandatory command makes `done` checkable and burdens every task.
4. Should `await` be the only blocking verb? `kodama task watch` would suit a dashboard.
5. One ladder for all types or one per type? Per type matches cost to difficulty; one ladder is cheaper to operate.
