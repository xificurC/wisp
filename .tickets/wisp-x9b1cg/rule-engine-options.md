# ember pivot — the orchestrator as a rule engine

Status: exploration for the owner. Round 1. No code. Nothing here is
settled. The owner picks the design; the pick lands in `ticket.md`.

Companions: `design-options.md` (round 4, with amendments) is the
prior design: a peer message bus. `api-spec.md` is its contract.
This document does not amend them. It explores the replacement the
owner asked for in round 7.

## 0. What changed

Sourced: the owner's message this session.

The old goal: N wisps that self-coordinate by addressed messages.
Useful as a feature, not useful for the owner's work.

The new goal: the owner defines agent types and rules between them,
submits a task, and the orchestrator runs agents by the rules until
the work settles. The general rules stay: concurrency cap, self-heal
on rate limit or outage, one view of all active and past runs.

The new mechanism: **decomposition** replaces delegation. An agent
splits its work into N runs plus one continuation, and the
orchestrator does the waiting. Agents add rules at run time through
the same API the owner uses at task set-up.

Cross-space coordination (two tasks, one file; an exclusive lock on
a database) is accidental complexity at scale. The owner defers it.
This document names its seam (§2.1) and stops.

## 1. First principles

### 1.1 What coordination is

Strip the names. A coordination system is one function:

```
history of finished work  ->  set of next actions
```

An action is: start a run, hold a job, steer a live run, stop a
run, retry a failed run. Everything else is plumbing: store,
transport, accounting, observation.

The design question is only: **where does this function live?**
Three homes exist:

1. In the owner's head. The status quo: `wispy` plus the gti
   methodology skills. Every step is a human turn.
2. Inside agents. The prior ember: each sender's message is the
   policy. The function is spread over N contexts, in prose.
3. Outside agents, as declared data. The pivot: a rule engine
   evaluates rows. Judgment wrote the rows; arithmetic runs them.

The three designs in §3–§5 are three readings of home 3, with home
2 kept as one of them (design B) for the cases that need judgment
per step.

### 1.2 The law that survives

Sourced: `design-options.md` §1, Q6.

The control plane holds no model. No queue, cursor, or slot waits
for an LLM. The bus runs at filesystem speed.

The pivot keeps this law and sharpens it. A rule engine is
arithmetic over rows. Rules are *written* by judgment — the owner at
set-up, an agent at decomposition time — then *evaluated* with no
model. Judgment moves to rule-authorship time. It never sits in the
evaluation path.

Cost consequence, sourced from the verified table (rounds 1–6): a
hard wake costs one turn; a steer into a live run costs no turn; the
merge window collects one burst into one wake. The transport cost is
known and fixed. The variable the owner actually pays is: **how many
sequencing decisions are model turns.** Home 1 pays one human turn
per step. Home 2 pays one sender turn per step. Home 3 pays zero:
each step is a row evaluation. Design B (§4) deliberately pays turns
to buy judgment.

### 1.3 Delegation versus decomposition

Sourced: the owner's message; the subagent recipes in the wisp
system prompt.

Delegation bundles two jobs:

- judgment: pick who does what;
- waiting: reap the result, then sequence the next step.

A top-level agent with subagents holds both. It stays live while the
children run. The live run burns a slot, and its context window
holds the waiting.

Decomposition splits the bundle:

- judgment happens once, at split time. The agent emits data: N
  child jobs plus one continuation.
- the emitted data is rules. The engine holds the waiting. The
  waiting costs no slot and no context.
- the continuation is a fresh run, woken by a join rule when the
  children settle.

The splitting run may end after the split. Its plan is rows in a
log, not prose in a context window. The price: the split must be
complete when made. The join shape is fixed at split time. Mid-flight
judgment needs a new rule, or design B.

### 1.4 Constraints that survive

All sourced, none assumed.

| #   | Constraint                                                                           | Source                      |
|-----|--------------------------------------------------------------------------------------|-----------------------------|
| C1  | no model in the control plane                                                        | design-options §1, Q6       |
| C2  | hard wake = 1 turn; steer to a live run = 0 turns; the merge window collects a burst | verified table, rounds 1–6  |
| C3  | one live run per session dir; the run lock W2                                        | invariants; wisp-changes W2 |
| C4  | delivery ack is a generic `wisp_steer_key`, never an exit code                       | S9; W1                      |
| C5  | guard 75 distills; a fallback model uses `wisp fork`                                 | round-5 amendments 6–7      |
| C6  | a body arrives only as a file; a job is a file                                       | round-5 amendment 1         |
| C7  | SQLite WAL, event-sourced, one writer                                                | S1                          |
| C8  | one hearth daemon per root, unix-socket CLI                                          | S2                          |
| C9  | cap 3, weighted fair share, the account bucket binds first                           | S6                          |
| C10 | cross-space exclusivity is deferred                                                  | the owner's message         |

## 2. The axes

Ten axes. The designs pick on the first six. The last four are
shared substrate in every design; the pivot does not touch them.

| Axis | Question | Varies? |
|---|---|---|
| X1 work unit | what one run is: agent type + job file -> typed result | shared |
| X2 sequencing authority | who computes the next action | **varies** |
| X3 rule language | workflow file, guardrails, or rule rows | **varies** |
| X4 rule mutability | who adds rules, when, in what scope | **varies** |
| X5 settle | when the task is done | **varies** |
| X6 decomposition | how a split is expressed and joined | **varies** |
| X7 governor | caps, fairness, rate-limit healing | shared (S6) |
| X8 transport | run/steer/continue; hard and soft; merge window | shared (the W-list) |
| X9 store, observation, authority | log, status, UI, socket identity | shared (S1, S2, S8, S10) |
| X10 cross-space claims | exclusive resources over tasks | deferred; seam named in §2.1 |

### 2.1 The deferred axis: cross-space claims

When two tasks touch one file or one database, the conflict is a
resource, not a message. The seam: one `claim` action plus
`resource.claimed` and `resource.released` events in the same store.
A rule may then wait on a claim. The claim table is the only
cross-task state. It stays out of v0 per C10. When it arrives, it
must live in the hearth: an agent-held lock dies with the agent.

### 2.2 The typed result

The engine can be mechanical only if run outcomes are typed. A
result is: artifact paths plus typed fields (verdict, splits).

Mechanism options (Q27):

- (a) the run calls `ember result set verdict=green` from its bash
  tool before it ends. The hearth writes the row; the log acks it.
  Sourced mechanism: members already reach the hearth through the
  socket (`api-spec.md` §3).
- (b) a structured tail convention parsed from `wisp response`.
  Cheaper for the agent, but the parse is a second truth.

Recommendation: (a). One writer, one truth. Assumed: the call costs
no extra turn, because it rides an existing tool round.

## 3. Design A — the Loom (declared workflow, dynamic splits)

- X2: the owner declares the whole workflow before the task starts.
- X3: a workflow file: stages, edges, loop predicates.
- X4: the owner writes rules at set-up; a run extends the graph
  only by decomposition.
- X5: settle = every terminal stage reached, no pending join.
- X6: a split plus a join-continuation, declared in the result.

Surface sketch:

```
ember space new task-123 --template ship
ember template write ship.md
ember task submit task-123 -F task.md
```

The template, for the owner's stated case:

```yaml
stages:
  design:
    {agent: designer, job: task.md}
  design-review:
    {agent: reviewer, after: design, job: out(design)}
  build:
    {agent: builder, after: design-review, when: verdict=green}
  review:
    {agent: reviewer, after: build, job: out(build),
     loop: {on: verdict=red, back: build, carry: notes,
            until: verdict=green, max: 5}}
  commit:
    {agent: committer, after: review, when: verdict=green}
```

Decomposition in A. The builder's typed result:

```
ember result set splits=jobs/m1.job,jobs/m2.job \
  continuation=agent:builder-join,job:jobs/join.tmpl
```

The engine creates group g7, starts two child runs (builder on each
job), and writes one join row. When both children are terminal, the
engine starts `builder-join` with the children's outputs as the job
input. The continuation may split again. Assumed: group cardinality
and depth caps mirror the spawn policy keys (`max_children`, depth).

Self-heal in A: a template-level retry clause, or the shared
governor policy (X7): on `run.failed reason=rate_limit`, requeue
with backoff; after two, `wisp fork` to the fallback model (C5).

Cost: zero sequencing turns. Audit: every run start names its stage
and the triggering result. `ember why <run>` prints the stage, the
edge, and the predicate values.

Limits: routing creativity is bounded by the file. Anything the
template does not name needs the owner, or a decomposition. Two
workflows in one space do not interact except through the governor.

## 4. Design B — the Foreman (one orchestrator agent, guardrail rules)

- X2: an agent computes the next action, per step.
- X3: no sequencing language. Rules exist only as guardrails and
  standing gates the engine enforces.
- X4: the owner writes guardrails; the foreman writes nothing
  durable except its own decisions in its log.
- X5: settle = the foreman's typed result `task.done`, or the task
  wallclock.
- X6: decomposition is delegation: the foreman spawns children, and
  the engine wakes the foreman when a child ends.

Surface sketch:

```
ember task new task-123 --foreman foreman.md --job task.md
```

`foreman.md` is one agent definition: a persona that reads state,
starts runs, and loops on review notes until green. The engine's
guardrails, sourced from the owner's stated general rules:

- cap: at most 3 live runs (C9);
- gate: a commit run requires a green review in the same task (Q31);
- heal: a rate-limited run requeues; twice means fork (C5).

The engine wakes the foreman on every child terminal: one standing
rule, `when run.finished in task-123 then steer foreman`. The
foreman is a member; the wake rides the verified transport (C2).

This is the gti `brain` + `methodology-basic` pattern, externalized
from the owner's terminal into a member. Sourced: those skills exist
and the owner runs them by hand today.

Cost: one foreman turn per sequencing decision. A five-stage task
with a two-round review loop costs about eight foreman turns on top
of the work turns. The foreman's context grows with the task.

Audit: prose in the foreman's log, plus guardrail rows for gates.
`ember why <run>` answers only for guardrail denials.

Limits: non-determinism and token cost scale with steps, not with
work. The foreman handles what no template can: "the CI failure
looks like a flake; rerun, do not rebuild." Judgment per step is the
product.

## 5. Design C — the Ledger (one rule table, uniform authorship)

- X2: anyone with scope rights: the owner at set-up, any run at any
  time, through one API.
- X3: event-condition-action rows over the event log.
- X4: rules carry scope (space / task / group), creator, expiry.
- X5: settle = quiescence: no enabled rule, no live run, no held
  job.
- X6: a decomposition is `rule.add` rows, scoped to the split group.

The rule row:

```
rule = { id, scope,
         when:  {event, predicate},
         then:   {action},
         created_by, reason, expires_at }
```

Events are typed rows the engine already writes: `task.submitted`,
`run.started`, `run.finished {agent, verdict}`, `run.failed
{reason}`, `result.set`, `rule.added`. Predicates are comparisons
over typed fields and counts (`children(g7) terminal == 2`). No
general computation. Actions: `start`, `steer`, `wake`, `stop`,
`hold`. Assumed: this predicate set covers the owner's stated
rules; Q30 verifies against the case list.

The owner's case as rows:

```
R1 when task.submitted
     then start designer job=task.md group=root
R2 when run.finished agent=designer
     then start reviewer job=artifacts(design) gate=design
R3 when run.finished agent=reviewer gate=design verdict=green
     then start builder job=task.md
R4 when run.finished agent=reviewer gate=build verdict=red
     then steer builder body=notes     # soft if live, hard wake if idle (C2)
R5 when run.finished agent=reviewer gate=build verdict=green
     then start committer job=artifacts(build)
R6 when run.failed reason=rate_limit
     then retry backoff=30s max=2 then fork     # C5
```

Decomposition in C. The builder ends with:

```
ember rule add --scope task-123/g7 \
  when 'children($scope) all terminal' \
  then 'start builder-join job=join(jobs/m1.job, jobs/m2.job)' \
  --reason "split: two modules"
ember start --agent builder --job jobs/m1.job --group g7
ember start --agent builder --job jobs/m2.job --group g7
ember left --reason "split into g7"
```

The owner uses the same verbs at set-up. The API is literally one
API, as the owner asked. The rows differ only in `created_by` and
`scope`.

Safety of the metasystem (rules that add rules):

- scope tree: space > task > group. A run may add rules only inside
  its own scope subtree. Assumed: enforced by the hearth, the one
  writer.
- caps: `rules.max` per scope, `firings.max` per task. A loop rule
  without a bound is rejected at write time.
- `rule.added` is itself an event; a rule may match it, so the
  acyclicity law is the firing cap, not structure.
- audit: `ember why <run>` prints the rule id, the event id, and the
  predicate values. Every row names its creator and reason.

Settle: quiescence. The engine computes: enabled rules = 0, live
runs = 0, held jobs = 0. A task that cannot settle parks for the
owner, with the blocking row named.

Limits: a rule language is a language. It will ask for variables,
aggregation, and time windows. Each addition is a spec decision.
The discipline: predicates stay comparisons; anything richer
belongs to an agent (design B composes, §6).

## 6. Comparison and composition

| Axis | A Loom | B Foreman | C Ledger |
|---|---|---|---|
| X2 authority | owner, upfront | foreman agent, per step | anyone scoped, any time |
| X3 language | workflow file | guardrails only | ECA rows |
| X4 mutability | owner + splits | guardrails by owner | uniform, scoped |
| X5 settle | graph fixed point | the foreman says done | quiescence |
| X6 decomposition | splits + join in the result | delegation | `rule.add` rows |
| sequencing turns | 0 | 1 per step | 0 |
| audit | stage + edge | prose + gates | rule id + event id |
| judgment per step | none (spent at authorship) | full | none (spent at authorship) |
| new risk | template ceiling | cost, context growth | language + metasystem |

Composition, the load-bearing claim of this document:

- C is the engine. A is sugar over C: a workflow file compiles to
  rows R1–R6. Nothing in A needs machinery C lacks.
- B is a persona over C: the foreman's wake-on-child-finish is one
  C rule; the foreman's `start` calls are C actions attributed to a
  member actor.
- So the three designs are not exclusive. The real choice is what
  to build first and what to expose first.

Recommendation, for the owner to accept or reject: build the C
substrate, expose the A surface in v0, admit B as one agent
definition when a case needs it. Reasons:

- the owner's stated rules — review loop until green, caps,
  self-heal — are all mechanical; they need no per-step judgment;
- decomposition needs scoped `rule.add`, which is C machinery. A
  alone cannot give the one API the owner asked for without growing
  a second rule path;
- B costs turns where the owner's cases need none;
- the language risk of C is bounded by shipping only A's predicate
  forms in v0, and refusing richer predicates until a case demands
  them.

Build order under the recommendation:

```
v0  store + hearth + typed results + the rule table
    (start, steer, wake, stop, hold) + pipeline sugar
    + split/join + cap 3 + retry/fork + `ember why`
v1  governor fairness + the claim seam, if scale arrives
v2  the foreman persona + guardrail gates
v3  UI: task graph view
```

## 7. What survives, dies, or morphs

Sourced: `design-options.md` seams and `ticket.md` gaps.

| Prior | Fate | Note |
|---|---|---|
| S0 standalone ember, stdlib | survives | unchanged |
| S1 SQLite WAL event log | survives | rule rows and result rows are new event kinds |
| S2 hearth + socket | survives | new ops: rule, result, start, task |
| S3 member record | morphs | a member becomes a run of a typed agent; no peer roster |
| S4 delivery classes | survives | the engine is the only sender; job / steer / hard-wake unchanged (C2, C4) |
| S5 peer addressing | dies in A and C | member `send`/`dm` go; B keeps them as foreman tools (Q34) |
| S6 governor | survives | cap 3, fair share, account bucket, 429 as ground truth |
| S7 spawn policy | morphs | spawn and start merge: the engine starts runs; approval gates become rule conditions |
| S8 observation | survives | the view becomes runs + rules + graph |
| S9 recovery | survives | steer-key ack, fork, distill (C4, C5) |
| S10 authority | survives | socket identity; actors are rule creators |
| S11 races | survives | run lock, steer lock, key dedupe |

Old gap questions: Q7 (account budget), Q8 (merge window), Q17
(router contract), Q21 (fork copy set), Q22 (steer expiry), Q23
(prompt key) survive as transport and governor questions. Q12 dies
into the obvious: the start action delivers the job as the run
prompt. Q13 morphs into rule expiry. Q15 and Q20 stay dead and
withdrawn. Q24 morphs: a steer is an engine action, not a member
verb. Q10 morphs into guardrail gates plus the owner claim seam.
Q14, Q16, Q18, Q19 keep their answers.

Names survive: ember (the space), hearth (the daemon), stoke (the
wake), `--andon`. Sourced: Q1, Q5.

## 8. Open questions

New rows Q25–Q34; they land in `ticket.md` ## Gaps.

| # | Question | Options | Rec |
|---|---|---|---|
| Q25 | Which design: A, B, C, or the composition? | (a) A only; (b) B; (c) C only; (d) C substrate, A surface, B later | d |
| Q26 | Rule authorship from a run: CLI verbs (`ember rule add`), typed result fields, or both? | (a) verbs; (b) fields; (c) both | a |
| Q27 | Typed results: `ember result set` before the run ends, a structured tail parsed from `wisp response`, or both? | (a) CLI; (b) tail; (c) both | a |
| Q28 | Join semantics: all, any, or quorum; and the continuation input shape? | (a) all + concatenated artifact digests; (b) any; (c) quorum | a |
| Q29 | Rule safety caps: `rules.max` per scope, `firings.max` per task, scope-subtree-only writes? | (a) all three; (b) caps only; (c) none | a |
| Q30 | Do comparisons-only predicates cover every rule the owner will write? | (a) yes, verify against the case list; (b) no, add aggregation; (c) no, add B for the rest | verify before v0 |
| Q31 | Is the review-before-commit gate a rule (R5) or a guardrail the engine enforces regardless of rules? | (a) rule; (b) hard gate; (c) both | c |
| Q32 | Where does the workflow template live: per space, a root library, or per task? | (a) root library, referenced by space; (b) per space; (c) per task | a |
| Q33 | Claim seam shape when cross-space arrives: hearth-local table now, shared later? | (a) defer, keep `claim` in the action set; (b) design now | a |
| Q34 | Does v0 keep any member-facing `send`/`dm`, or is the engine the only sender? | (a) engine only; (b) keep `dm` for B | a |

## 9. Sources and assumptions

Sourced: the owner's message this session (the pivot; the deferred
cross-scale problem); `design-options.md` rounds 1–5 (laws, seams);
`api-spec.md` (socket protocol, agent definitions); `wisp-changes.md`
(the W-list); `ticket.md` verified table (transport facts); the gti
skills `brain` and `methodology-basic` (the manual-foreman prior
art); C1–C10 as cited inline.

Assumed, each with its check: a typed result by CLI call costs no
extra turn, because the call rides an existing tool round (check:
one fake-endpoint run with a result call); comparisons-only
predicates cover the owner's stated rules (check: Q30, against the
owner's case list); the hearth evaluates quiescence and enabled
rules as SQLite arithmetic (check: a unit test on a temp store);
the group join is a COUNT over terminal children (same check).
