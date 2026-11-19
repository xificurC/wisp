# ember pivot — the rule language

Status: round 18. Round 9 answered the language axes (Y1–Y13) and the
eight findings; round 10 answered six follow-ups (the steward's own
steering, the closure of a decomposed run, the `-F` input contract, a
request-time `<environment>`, and syscall-level file capture). Rounds
13–17 added the exhaustion recipe and its two loops in `ticket.md` and
`ember/README.md`; round 18 adds the three run targets (`--run`,
`--resume`, `--fork`) and the two rule policy flags (`--guard`,
`--wallclock`). This document carries the amended definition. No code.

Sourced: the owner's round-9 message (answers Y1–Y13, F1–F8) and
round-10 message (six follow-ups); the round-8 review kept in git
history and in §0; `rule-engine-options.md`; `design-options.md`
R4/R5; `ticket.md` `## Verified`; `wisp/wisp` `new_session` 209–240,
`steer_command` 857–878, `body_of_*` 3676–3860; nono v0.80.0; the
round-9 probes in §6.2 and the round-10 probes in §6.3.

## 0. What changed in rounds 9 and 10

| Owner's answer | Design change | Section |
|---|---|---|
| Y5: "VERBs are not fixed (`--require` adds a field)", `--event agent-type:verifier.passed`, `agent-type:foo.count>3` | the verb set is open: a required result field **is** a verb, and a verb may carry a comparison test | §4.1, §4.3 |
| F1: "the cap needs to be an expression", `--cap agent-type:design-verifier.done<3` | a cap counts atoms matching an expression against a threshold, not firings of the rule | §4.4 |
| Y4: a type is `wisp new -d <space>/agent-types -s <skill>`, "can be forked" | an agent type **is a wisp session dir**; no type file format; a run is a `wisp fork` of the type | §4.7 |
| F3: existence check, one re-prompt, "versioning – OK", "it needs to change (diff)" | `--out` is a checked contract with three failure reasons and a comparison against the previous cell version | §4.2, §4.3.1 |
| F4: "we need `ember steer`… the engine then starts a steering agent" | injection into a live run dies; the engine never calls `wisp steer`; W1 is not needed. **Round 10 reverses the W1 half**: a joined steer and the steward's own `wisp steer` bring two writers to one inbox, so the lock returns (§4.8) | §4.8, §7 |
| Y6: "not sure what interface inheritance means" | drop it: a restart re-declares its `--in`/`--out` | §4.2 |
| Y2: negation, pairing, aggregate counts "may become useful… throwing stub" | `rule add` refuses each by name; consumption stays because F1 needs it | §4.1 |
| Y7, Y8, Y12: defer, "enough metadata… later", "only what's necessary for v1" | cap scope, park, slots, and grants stay out; every mutation records its creator | §4.9 |
| F8: "just per-space for now" | the root rule library dies in v0 | §4.4 |
| F2: "already solved above" | the outcome domain lives on the **rule** (`--require`), not on the type | §4.3 |
| F5 accepted, F6 skipped | run row + run lock + typed result carry recovery; grants deferred | §3.5, §4.9 |
| F7: "scout for other options that can track file addition/change/removal precisely" | round 9: per-run working tree plus a stdlib snapshot diff. **Superseded in round 10**: strace `-ff` with a curated syscall set is the recorder (§6.3); namespaces stay unavailable on this host | §6 |
| Y13: "the rule is durability — even after an unexpected death the system must be able to start up to the same state" | one committed log per space; a start is two-phase; the startup scan reconciles | §4.10 |

Three of these overturn a round-8 proposal: F2's domain on the type
(now on the rule), F4's conditional steer (now a plain start), F8's root
library (now deferred). Two of them overturn an example the owner
wrote, because the owner's later answer changed the vocabulary:
`agent-type:design-verifier.done` in the F1 cap example is not a verb
any more, and reads `agent-type:verifier.passed<3` under §4.1.

### 0.1 Round 10

| Owner's point | Design change | Section |
|---|---|---|
| the steward may `wisp steer` live runs; a second steer while a steward is live may join it | the engine's only transport is a start, except a steer atom, which joins a live run of the target type; an agent's transport is a steer; the steer lock (W1) returns to the required set | §1.3, §2.1, §4.8, §7 |
| give the best possible `no_result` message | every failure reason gets a named report: field, type, run, rule, version, trigger atom, times, re-prompt, fix command | §4.3.1 |
| `.done` on a type must mean the root and all children | every run carries an inferred parent; `agent-type:T.done` is a root closure atom; `agent-type:T.failed` stays a per-run fault; a repair stops a failure poisoning its tree | §4.11 |
| simplify the fork's record rewrite | the `<environment>` block renders at request time from `wisp.run.json` and `-d`; `fork` becomes a plain copy | §4.7, §7 (W13, W7) |
| every `ember` verb takes its body the same way | `-F FILE` or `-F -` only; no verb reads bare stdin; argv carries scalars and labels | §4.12 |
| syscalls, not a snapshot diff | `strace -ff -y` around every engine-started run, curated syscall set; the work dir stays for outputs, not for attribution | §6.3 |

### 0.2 Round 18

| Owner's point | Design change | Section |
|---|---|---|
| "`--run` runs a new agent; we need a `--something` that resumes, re-prompts, continues the agent" | a second target, `--resume`, sends one more prompt into the trigger run's own session with `wisp run -d <the same dir>`; the type and persona are the source's | §4.1, §4.13 |
| "we can also have a `--fork`" | a third target, `--fork`, sends the prompt into a copy of the trigger run's session and work dir; the source log stays frozen and the stopped point can branch | §4.13 |
| "I'm fine adding `--context-guard` and `--wallclock` to the rules" | `--guard LIMIT` and `--wallclock S` are rule flags, copied to the run row; the guard must leave room for the resume turn | §4.13 |
| "the point was to support continuing a stopped run" | the round-17 resource store is dropped: the prompt is the rule's body, entered through `-F`; a continuation is a repair over the source run | §4.11, §4.13 |

### 0.3 Round 19

| Owner's point | Design change | Section |
|---|---|---|
| "wallclock stop is a failure, period" | no contract check after exit 124; `reason=wallclock` is terminal and the space-level rescue is the only continuation (N13) | §4.13 |
| "session-file and resource make sense" | `--out` takes `session-file:NAME` or `resource:NAME` and refuses any other category; a `resource:` output lands in `<space>/resource/` and the cell store versions it like any other (N14) | §4.2, §4.13 |
| "allow model and thinking settings" | `--model M` and `--thinking T` are rule flags, passed to `wisp fork -m/-t`, so they cover every target that forks a dir; `--resume` forks nothing and refuses both (N18) | §4.13 |
| "yes" to the fault atom's value | `run:<id>.failed` and `agent-type:T.failed` carry `value=reason`, so `--event agent-type:T.failed=guard` selects and a cap can count one reason (N19) | §4.3, §4.13 |

### 0.4 Round 20

| Owner's point | Design change | Section |
|---|---|---|
| "if we split the rules into agents and rules, it could come off cleaner" | an agent row is a named run contract (`ember agent add`); a rule keeps event, target, and cap; `--run agent:NAME` starts it and a rule-level `--in` extends its inputs (N20, proposed) | §4.14 |
| "the inheritance is clearly visible for the continue" | `--run agent:pickup --in session-file:handoff.md` inherits type, require, out, guard, wallclock, and model from the agent row, so `.parent` leaves the recipes | §4.14 |
| "we discussed putting the distill prompt in as a resource" | the round-18 settlement stands (N15 d: no resource store), and the prompt moves to the agent row's body, which is named and versioned where a rule body was not | §4.14 |
| "when done (success or failure), run a reviewer" | the event needs a disjunction, ` or ` between alternatives (N21, proposed); today two rules over one agent do the same | §4.14 |
| "at most 3 times" for both loops | the distill loop's budget counts `agent-type:worker.failed`, not handoffs: a failing resume writes no handoff, so the round-19 `handoff<3` cap never blocks it | §4.14 |

### 0.5 Round 21

| Owner's point | Design change | Section |
|---|---|---|
| "`agent-type:reviewer.approved<4` — is it a count of the approved key?" | yes: a cap counts matching atoms space-wide and `N` is the threshold; the value of `approved` is not compared. The spelling hides that, so the required form is `count(EXPR)<N` and the bare form is refused (N23, settled in round 22 and landed in `ember`) | §3.1, §4.4, §4.14 |
| "why not `agent-type:reviewer.ran`, where `ran` is a counter of runs?" | a counter atom is a derived fact with a writer: it drifts when a counter write is lost, and it counts starts rather than finished runs; a count over terminal atoms is arithmetic and cannot drift | §8 (N23) |
| "the `continue` rule need not give `--in task:prompt` again" | right: a rule's `--in` **extends** the agent's inputs, exact repeats dropped. §4.14 said "replaces", which would have dropped the task, and its own example already assumed inheritance | §4.14 |
| (found by probe) `approved<4` in `--event` matches every approved atom | the matcher coerces bool to int, so `int(False)=0<4`; make matching type-strict and refuse at `rule add` a comparison the declared field type cannot satisfy. `agent-type:worker.failed<4` never matches a string reason | §4.1, §4.14 |

### 0.6 Round 23

The owner read the `ember` README and found two faults: it never showed
an agent definition, and `--out` looked useless, because every example
named one session file and a run already has a delivery channel in its
final assistant message.

| Owner's point | Design change | Section |
|---|---|---|
| "`--out` seems useless; in every example it names a single session file" | accepted: a run delivers by its **answer**, the final assistant text, read from `<run dir>/wisp.jsonl` and written into the next briefing as an `answer:` block. `--out` is withdrawn, and with it `session-file:`/`resource:` outputs, `no_output`, `no_change`, `--in .out`, and the space `resource/` folder | §3.3, §4.2, §4.5 |
| "an agent already has an implicit delivery channel — the final assistant response" | the engine reads it at firing time, so the reader needs no flag. The answer travels in full to 16 KiB, then as head and tail with one line naming `ember query run:<id> --json`; a trigger run with no text prints `answer: none (...)` | §4.5, §4.6 |
| "default rules to inject the triggered agent's response as input" | one reader, no declaration: every firing whose trigger names a run carries that run's answer. `--in` keeps naming space cells (`task:prompt`, `steer:last`), and a `.` reference in `--in` is refused with a message naming the default | §4.2, §4.12 |
| the contract that `--out` carried (F3) | the answer is the checkable half, and `wisp` already refuses a textless turn with exit 79, so the engine's new gate (`no_response`, one re-prompt) fires on the crash-and-adopt path, not on a normal empty turn; `--require` stays the typed half (`no_result`) | §3.3, §4.3 |

Consequences: a run's artifacts are its work-dir files, recorded by the
trace and readable through `ember query run:<id> --files all`; the space
owns cells only for `task:` and `steer:`; and a rule row's `outputs`
column holds `[]` forever, so old stores read unchanged.

N24 settles the drop. Q35 (F3's contract) is superseded for files and
survives for fields; N3 (one cell name per rule) dies with the cells;
N14 (the two `--out` categories) is void. The examples in §4.13, §4.14,
and §5 are the round-18, round-19, and round-20 records: their `--out`
and `.out` tokens read as the answer channel.

### 0.7 Round 27

The owner settled the daemon's scope and the store's scope: one global
hearth (N27 a) and one database for all spaces (N28 a), overriding
N27 (a)'s per-space-stores clause. Both are code in `ember/ember`.

| Fact | Design change |
|---|---|
| one daemon per user | `ember hearth start` takes no space (round 29: `ember daemon start`); the socket, the pid, the log, and the database live at `EMBER_STATE_ROOT` (default `~/.local/state/ember`), 0700; the request payload carries the space, resolved by the CLI from `--space`/`EMBER_SPACE` |
| one database | every table (`atoms`, `rules`, `runs`, `consumed`, `joins`, `cells`, `files`, `meta`) and every fixed meta key gains a space binding — the space's directory path — and a `spaces` registry table (id, path, paused, created) maps the path to a display id and the pause flag |
| the cap is global | `admit` counts live runs across every space and picks pending rows round-robin (`next_pending`, cursor on the daemon), so one hungry space cannot starve another and a slot freed in one space starts a pending run in another |
| a space can be held | `ember space pause` and `unpause`: a paused space's pending rows are skipped by admission while its rules still fire; `reconcile_all` iterates the registry at daemon start |
| portability | `ember space export [-o FILE]` writes one space's control-plane rows as JSON; `ember space list` prints the registry; content stays per space on disk |
| what globalizes | `atoms.seq` and run ids: one increasing seq orders events across spaces (per-space order survives by filtering), and run ids are collision-checked in the one file |
| what stays per-space | rules, atoms, cells, trees, steers, briefings — a rule id, a cell name, and an agent type name may repeat across spaces, and every query filters by the binding; the round-7 cross-space isolation stays physics |
| what is lost, bought deliberately | the space directory stops holding its own control plane, so `rm -rf` leaves orphan registry rows and a moved directory is a new binding; export is the escape hatch. Per-space stores from rounds 12-26 are not migrated |

### 0.8 Round 29

The owner retired the metaphor for the process and kept it for the
data: the verb is `ember daemon start|stop|status`, and every file in
the state root is named `ember.<kind>` (N29 b). The sections above keep
`hearth` where they record their own round; read `hearth` as `daemon`
from here on.

| Fact | Design change |
|---|---|
| one name per thing | `daemon` names the process and only the process, so the word appears in verbs and prose and in no file name; `ember` names the program and every file it writes |
| the state root | `ember.db`, `ember.sock`, `ember.pid`, `ember.log` at `EMBER_STATE_ROOT` (default `~/.local/state/ember`, 0700). The directory already carries the program name, so `ember/ember.sock` stutters and stays: `EMBER_STATE_ROOT` relocates the four files out of that directory, where the stem still says whose state they are |
| one stem to remember | four files, one rule — `<program>.<kind>`, as `/var/run/docker.sock` and `nginx.pid` name a program's state rather than the program's role |
| the code follows the name | `Hearth` becomes `Daemon`; `hearth_alive`, `call_hearth`, and `command_hearth` become `daemon_alive`, `call_daemon`, `command_daemon`; the dead `require_hearth` is dropped; `Hearth.pump` and `Hearth.poll` above read `Daemon.pump` and `Daemon.poll` |
| no second writer on upgrade | a daemon built before the rename bound `<root>/hearth.sock` and writes the same `ember.db`, so `daemon start` sends it `shutdown`, waits for its socket to stop answering, clears `hearth.sock` and `hearth.pid`, carries `hearth.log` to `ember.log`, and refuses to start (exit 1, naming the pid file) when the old daemon does not stop |
| no alias | `ember hearth` is gone and argparse answers exit 2; the old word survives only in three legacy-name constants and in the documents' round records |

Consequences: N29 settles as (b). The round-2 naming keeps `ember`,
`stoke`, and `--andon`, and loses `hearth` for the process. The `ember
hearth start` spelling in §0.7 and in the N29 row of §8 is the round
record of the surface that shipped before this rename.

## 1. First principles

### 1.1 Three primitives

- **Atom**: an immutable fact. Subject, verb, and typed fields. The
  subject is `space`, `me`, `run:<id>`, `id:<rule>`, or
  `agent-type:<type>`. The verb is one of a small fixed set or a
  declared result field.
- **Edge**: a rule. An atom expression, an agent type, input
  references, required result fields, output declarations, a cap.
- **Cell**: a named, versioned pointer in the space.

`--id job1` is an edge with a name. Decomposition is edges over the
run-end atoms of other edges. The user steer is an atom plus an edge.

### 1.2 The engine keeps six tables

`atoms`, `runs`, `cells`, `rules`, `firings`, and `files`, all in one
SQLite WAL database per space, all derived from one append-only log. A
firing row is the audit unit; `ember trigger show` prints one. `files`
holds the parsed syscall rows of §6.3.

### 1.3 Two transport acts, one narrowed to one rule flag

Round 8 assumed two acts: start a run, steer a live run. The owner's F4
answer removes the second for the engine. **A start is the engine's only
transport**, with one exception that needs no flag: a **steer** joins. A
firing whose trigger is `space.steer` appends its inputs to a live run
of the target type instead of starting a second run, and starts one only
when none is live (§4.8). **An agent is not the engine:** a steward run is a
model with bash, so it may `wisp steer` any live run in the space, and
its words land as data in that run's inbox. The price is unchanged: a
burst to a joined target is not merged, and a wrong liveness guess costs
one run.

### 1.4 Liveness is the one fact that is not an atom

A run's liveness is the run lock (W2). With the ack dropped it is the
only cheap answer to "is this run alive" after a restart.

### 1.5 Constraints

| # | Constraint | Fate |
|---|---|---|
| C1 | no model in the control plane | survives |
| C2 | a run costs its turns | survives |
| C3 | one live run per session dir | survives; a forked run dir per run keeps it |
| C4 | steer-key ack | dies |
| C5 | guard 75 distills; fork for a fallback model | survives |
| C6 | every input is a path | survives |
| C7 | SQLite WAL, one writer | survives; **round 27: one database for all spaces** |
| C8 | hearth daemon plus socket | survives; **round 27: one daemon per user, not per space** |
| C9 | cap 3 plus fair share | survives; **round 27: the cap counts live runs across every space, admitted round-robin** |
| C10 | cross-space claims deferred | survives |

## 2. The axes, answered

| Axis | Owner's answer | What it fixes in v0 | What stays out |
|---|---|---|---|
| Y1 atom vocabulary | the open atoms are valid | `space.submitted`, `space.steer`, `space.settled`, `run.started`, `run.done`, `run.failed`, `rule:<id>.capped`, one atom per required result field, plus the two type atoms of §4.11: the per-run fault `agent-type:T.failed` and the root closure `agent-type:T.done` | none |
| Y2 pattern algebra | stubs for what is not known | conjunction, per-rule atom consumption, one comparison test per atom | negation, `or`, two multi-subject conjuncts, aggregate counts in `--event`; `rule add` refuses each by name |
| Y3 cells | "keep out" | names, versions, `--out` injection, latest-version resolution, firing pins the version read | `{trigger}` substitution; collision policy beyond last-write-wins |
| Y4 run interface | a type is a `wisp new -d … -s …` session dir, "can be forked" | type = session dir; run = `wisp fork` of it; briefing names inputs, outputs, required fields | type sidecar metadata, prompt template, environment |
| Y5 outcome typing | `--require passed:bool`, `--event agent-type:verifier.passed`, `agent-type:foo.count>3` | field verbs, tests, required-field policy | a field type beyond `bool`, `int`, `str` |
| Y6 lineage | "works the same after a restart", ids unique, no interface inheritance | `me`, `.parent`, `id:`, unique `--id`, restart re-declares | inheritance |
| Y7 bounds | "dunno yet" | the cap expression (F1) | counter scope, park, per-type slots |
| Y8 authority | metadata now, grants later | creator, run, version, disabled-by on every mutation | grants, root layer, disable-vs-delete policy |
| Y9 lifecycle | quiescence; park and cancel later | settle predicate and `space.settled` | park, cancel |
| Y10 steer path | `ember steer` plus a new steering agent | atom → rule → steward start, or a join into a live steward when one is running; the steward may `wisp steer` a live worker | engine injection into a worker, a per-type steward slot |
| Y11 governor | not understood; cap 3 stays | cap 3, pending actions | per-type slots, invisible rate-limit healing |
| Y12 observation | "only what's necessary for v1" | `trigger show`, `query`, `space show`, advisory file list from the syscall trace (§6.3) | selectors beyond the listed fields, UI |
| Y13 store and recovery | "the rule is durability" | committed log, two-phase start, startup reconciliation | nothing |

### 2.1 Y10 in plain words

Round 8 asked two questions the owner did not follow. Both are dropped,
and here is what they meant, so the removal is on the record.

- **Injection versus restart.** To change a live run's behaviour you
  can append a message to the run's inbox (`wisp steer`); the run reads
  the message at its next round boundary. That is injection: no new
  run, no new turn, no guarantee (the line can land after the run
  ends). The other way is restart: start a new run with the message as
  an input and leave the live run alone. The owner's answer is restart
  for the engine: `ember steer` writes an atom and the engine starts a
  steward run. The engine calls `wisp steer` in one place only: the join of a
  steer atom into a live run of the rule's target (§4.8).
- **An agent may still inject.** The steward run is an ordinary agent
  with bash. It reads `ember query runs`, picks a live run directory,
  and runs `wisp steer -d <dir> < msg.md`. That is data handed to a
  model, not a routing decision, so the control plane's determinism is
  untouched. Round 10 makes this explicit rather than accidental.
- **Steward concurrency.** Round 9 deferred a per-type slot. Round 10
  removes the need: a steer joins, so a second steer appends to the live
  steward instead of starting one. Two steers a minute apart cost one
  steward run, not two, and no slot is needed. Y7 stays deferred for
  other types.

### 2.2 Y11 in plain words

- **Pending action.** A rule fires while all three run slots are taken.
  The firing is recorded and waits; it is not dropped. Without a
  pending state a full cap loses work.
- **Per-type slot.** A maximum number of concurrent runs of one agent
  type, independent of the global cap 3. Deferred.
- **Invisible healing.** A rate-limited run is retried on a fallback
  model by the engine with no atom and no surface change. Deferred; the
  owner's rule is that the log shows what happened.

## 3. The findings, answered

| # | Verdict | Effect |
|---|---|---|
| F1 caps loop | accepted, with a cap expression | §4.1, §4.4 |
| F2 binary outcome | accepted as "solved above" | field verbs replace the mapping; the domain lives on the rule, not the type |
| F3 unchecked output | accepted and extended | existence, one re-prompt, versioning, and a change check |
| F4 fragile steer | accepted in part | `ember steer` exists; the conditional steer and `wisp steer` do not |
| F5 recovery | accepted | run row, run lock, typed result |
| F6 authority | skipped | flat authority, metadata recorded, grants deferred |
| F7 change capture | re-scouted | §6 |
| F8 generic rules | per space for now | the root library is out of v0 |

### 3.1 F1 — consumption and the cap expression

Accepted. Two parts, and the second is new.

- **Consumption.** An atom fires a rule at most once. Consumption is per
  rule, not global, so the decomposition example still lets two rules
  read the same `me.done` atom.
- **The cap is an expression, and the expression is wrapped.**
  `--cap 'count(EXPR)<N'` counts the atoms that match `EXPR` in the
  space and blocks the firing at the threshold:
  `--cap 'count(agent-type:verifier.passed)<3'` allows three green
  verifications. When only one rule can produce the counted atom, the
  count equals the rule's firings; when several rules can, the count is
  the space's, and the owner's "then it could be per id" scopes it with
  an `id:` subject (`count(id:pickup.done)<3`), which
  `count_cap` resolves through the rule as a firing does.
  The owner's own example, `agent-type:design-verifier.done<3`, is
  written before Y5 replaced `done` with declared fields; under §4.1 it
  reads `count(agent-type:verifier.passed)<3`. The wrapper is required
  (N23, settled round 22): a bare `agent-type:reviewer.approved<4` reads
  as a comparison on the atom's value, and a value test of its own goes
  inside the count, `count(agent-type:reviewer.approved=false)<4`. The
  two grammars therefore never collide: `--event` tests one atom's
  value (`agent-type:reviewer.defects>5` on a `--require defects:int`),
  `--cap` counts atoms whose value passes such a test.
- At the threshold the engine writes `rule:<id>.capped` once and stops
  firing the rule. Park and report are Y9's deferred part.

### 3.2 F2 — where the outcome domain lives

Answered by Y5, and the answer is the opposite of the round-8
proposal: the domain lives on the **rule**, because `--require` is a
rule flag. The agent type carries no result contract. The consequence
is a small hole: two rules over one type may require different fields,
and the engine cannot notice. §8 asks the owner whether the type should
carry a default set.

### 3.3 F3 — the contract on a run's delivery (withdrawn in round 23)

Round 9 accepted `--out` with three additions: the path is injected in
the briefing, a missing file costs one re-prompt then `no_output`, a
byte-identical file costs one re-prompt then `no_change`, and every
write binds a cell version.

**Round 23 withdraws the whole file contract.** A run already delivers
through its final assistant message, so `--out` was a second channel
that every example pointed at one file. The engine reads the answer
(§4.5) and keeps two failure reasons: `no_response` when a finished run
left no text, and `no_result` when a declared field was never set. Each
costs one re-prompt. `wisp` refuses a textless turn with exit 79 before
the contract is reached, so `no_response` surfaces on the crash-and-adopt
path, where a killed run set its fields but never answered.

The versioned-cell machinery lives on for the two cells the space owns
(`task:`, `steer:`), not for run outputs. A run's files are its own: the
trace records them and `ember query run:<id> --files all` reads them.

### 3.4 F4 — the steer is a start

Accepted in the owner's form, not the round-8 form. `ember steer -F
msg.md` writes `space.steer` and a `steer:` cell. A space rule starts
the steward type. The steward orients, inspects runs and rules, and
adjusts the space through the same rule API. The engine touches no live
worker run, so no worker message can be lost.

Round 10 adds the two things this paragraph left out. A second steer
joins a live steward instead of starting a second run, and a steward run
may itself `wisp steer` a live worker. Both
change the last sentence: the engine touches no live worker, and one
inbox now has two writers, so W1's lock is required (§4.8).

### 3.5 F5 — recovery without an ack

Accepted. A run row in a non-terminal state plus a free lock means the
run is over: a result row makes it done, otherwise failed with
`reason=crashed`. A held lock means alive; the daemon adopts the run.
The run row is written before the spawn, in the same transaction as
`run:<id>.started`.

### 3.6 F6 — deferred

The owner wants metadata now and policy later. v0 records the creator
(`owner` or `run:<id>`), the rule version, and the disabling run on
every mutation, and enforces nothing. Any run may disable any rule; the
audit names it.

### 3.7 F7 — re-scouted

§6. Round 9's short answer was a per-run working directory, so a
directory diff is exact by construction. Round 10 replaces it: a
directory only shows writes the engine already owns, so the recorder is
a syscall trace (§6.3). nono is not the recorder in either round.

## 4. The definition (amended)

### 4.1 Grammar

```
EMBER_SPACE=<space dir>

ember space submit -F prompt.md
ember space show
ember steer -F msg.md [--reason TEXT]

ember rule add --event EXPR (--run TARGET | --resume | --fork)
               [-F BODY] [--require FIELD:TYPE]...
               [--in REF]... [--out CELL]...
               [--cap 'count(EXPR)<N'] [--id ID] [--reason TEXT]
               [--trace files|none] [--guard LIMIT] [--wallclock S]
ember rule disable --id ID [--reason TEXT]
ember rule list

ember result set FIELD=VALUE
ember trigger show [--run RID]
ember query run:<id> | runs | rules | cells [--json]

EXPR    := ATOM ('and' ATOM)*
ATOM    := SUBJECT '.' VERB [TEST]
TEST    := ('=' | '!=' | '<' | '<=' | '>' | '>=') LITERAL
SUBJECT := 'space' | 'me' | 'run:' RID | 'id:' ID | 'rule:' ID | 'agent-type:' TYPE
VERB    := 'submitted' | 'steer' | 'settled' | 'started' | 'done'
         | 'failed' | 'capped' | FIELD
TARGET  := TYPE | '.' 'parent'      ('.resume' and '.fork' are the
                                    stored forms of the two flags)
REF     := '.' FIELD | CELL
CELL    := CATEGORY ':' VALUE
FIELD   := an identifier declared by --require
TYPE    := 'bool' | 'int' | 'str'
```

Eight rules make the grammar unambiguous.

1. `.` separates a subject from its verb and nothing else; a leading `.`
   marks a backreference.
2. `:` composes a value into a subject, a cell, or a field requirement.
   `--in task.prompt` is `--in task:prompt`, because `task.prompt`
   already reads as an atom in `--event` position.
3. Position decides the role: `--event` reads an expression, `--in`
   reads a reference, `--out` declares a cell, `--require` declares a
   result field, `--run` names a type or the parent, and `--resume` and
   `--fork` name no type because they inherit the trigger run's (§4.13).
4. **The verb set is open.** A field declared by `--require` is a verb.
   `--require passed:bool` makes `agent-type:verifier.passed` legal.
   The fixed verbs belong to the engine and to the space only.
5. **A verb may carry one test.** `agent-type:foo.count>3` compares the
   field's value. A bare field verb means `true` for a bool field and
   "present" for `int` and `str`. `=`, `!=`, `<`, `<=`, `>`, `>=` are
   the whole operator set.
6. `id:X` names the run that rule X started, so `id:X.done` is a run-end
   atom and never "rule X fired". A rule that may fire more than once
   cannot be named by `id:`; `rule add` checks.
7. **The fixed verbs are scoped to their subject.** `submitted`,
   `steer`, and `settled` are `space:` only. `started`, `done`, and
   `failed` are `run:` and `id:` only, with two exceptions on a type
   subject: `agent-type:T.failed` is the fault atom for a run of T that
   ended without its required fields, and `agent-type:T.done` is the
   closure atom for a root run of T whose whole tree is green (§4.11).
   `capped` is `rule:` only.
8. **One target per rule.** `--run TYPE` starts a fresh agent,
   `--run .parent` starts the type of the trigger run's parent,
   `--resume` continues the trigger run's own session, and `--fork`
   continues a copy of it. `rule add` refuses two targets, a
   `--resume` or `--fork` without a conjunct that names a run, a body
   on `--run`, and a `started` conjunct with a continuation, because a
   source is continued at a run end (§4.13).

Three rule flags carry policy rather than grammar: `--trace
files|none` (§6.3), `--guard LIMIT`, and `--wallclock S` (§4.13). The
join of a steer is not a flag; it follows from the atom's subject
(§4.8).

Refused at `rule add` with a named error, per Y2: `or`, `not`,
aggregate counts in `--event` (`space.done*3`), and a conjunction whose
conjuncts name two multi-run subjects (`agent-type:a.done and
agent-type:b.done`). Each refusal prints `not implemented in v0: <what>`
and the accepted alternative.

### 4.2 Cells

- Categories: `task:` (immutable inputs), `steer:` (a message),
  `result:` (a typed field). Round 23 removes the two file categories
  with `--out`: a run delivers by its answer (§4.5).
- A cell name is space-scoped. Every content change binds a new
  version. A name resolves to the latest version at firing time; the
  firing row pins the version it read.
- Only the space writes cells in v0: `task:prompt` from `space submit`
  and `steer:last` from `ember steer`. `--in` names a cell and the
  briefing prints the resolved path and version.
- A rule may not name a run's output. `--in .out` is refused at
  `rule add` with a message naming the default: every firing whose
  trigger names a run carries that run's answer.
- The two failure reasons left are `no_response` (the run left no
  final message) and `no_result` (a required field was never set).
  Each costs one re-prompt.
- A restart (`--run .parent`) **re-declares** its `--in`. There is no
  inheritance (Y6). A restart that omits an input reads nothing; the
  audit shows the difference.
- No `{trigger}` substitution (Y3). One name accumulates versions, and
  the firing row pins the version read.

### 4.3 Outcome typing

The engine writes data atoms from declared fields, never from prose.

- `--require passed:bool` on a rule puts `passed` in the briefing's
  close line. The run sets it with `ember result set passed=true`.
- The engine writes one atom per required field:
  `agent-type:<type>` `.passed`, with `passed` in the atom's fields.
- A missing field costs one re-prompt, then `run:<id>.failed` with
  `reason=no_result`, and no data atom.
- `run:<id>.done` and `run:<id>.failed` are engine facts about the
  process and exist for every run, whatever the fields.
- `agent-type:T.failed` is the fault atom for a run of T: the run ended
  without its required fields, whether from a crash, `no_output`,
  `no_change`, `no_result`, or a guard 75. It fires per run, at the
  moment of the fault, at any depth, because a repair rule cannot wait
  for a tree to settle (§4.11).
- `agent-type:T.done` is the closure atom for a root run of T (§4.11).
  It is not a per-run success fact; `run:<id>.done` carries that.

### 4.3.1 The failure report

Every failure reason prints the same shape, because the shape is what
makes a failure actionable. The engine writes the text to the run's row,
prints it from `ember query run:<id>`, and puts the same fields on the
fault atom, so a rule and a person read one record.

```
run r-d3f2 failed: no_result
  field:        passed:bool
  type:         verifier
  rule:         verify-design v3
  trigger:      atom 41  agent-type:designer.ok
                from run r-d1a (designer) at 2026-11-17T16:40:02Z
  started:      2026-11-17T16:40:03Z
  ended:        2026-11-17T16:41:19Z (76s, exit 0)
  re-prompt:    1 of 1 at 2026-11-17T16:41:22Z
  results set:  ok=true, passed missing
  workdir:      <space>/work/r-d3f2
  last words:   "The design is sound; I updated the checklist."
  fix:          ember result set passed=true
```

The same record for the two output reasons, so one parser covers all
three:

```
run r-d3f2 failed: no_change
  cell:         session-file:design-verification.md
  type:         verifier
  rule:         verify-design v3
  expected:     a content change from version 2
                sha256 9f2c1a…  written 2026-11-17T15:02:11Z
  found:        byte-identical content
                <space>/work/r-d3f2/design-verification.md
  re-prompt:    1 of 1 at 2026-11-17T16:41:22Z
  fix:          edit the file, then re-run the rule
```

```
run r-d3f2 failed: no_output
  cell:         session-file:design-verification.md
  expected:     <space>/work/r-d3f2/design-verification.md
  found:        missing
  re-prompt:    1 of 1 at 2026-11-17T16:41:22Z
  workdir:      <space>/work/r-d3f2
```

The atom carries the machine fields and no prose:

```
run:<id>.failed         reason=no_result  missing=passed:bool
                        type=verifier  rule=verify-design  rule_version=3
                        started=…  ended=…  exit=0  reprompt=1  workdir=…
agent-type:<type>.failed  the same fields, plus run=<id>
```

Three details make the message useful rather than merely correct.

- **The field name, the type, the run, the rule, and its version** are
  always present, because two rules can demand different fields of one
  type (N1) and the version is what makes the failure reproducible.
- **The trigger atom** is named with its seq and the run that produced
  it, so the reader can walk from the failure to the input that caused
  it without a second query.
- **The last model words** are a 200-character excerpt of the run's last
  assistant record. The field is missing because the model forgot; the
  excerpt is the cheapest evidence of what it thought it did.

The re-prompt names the exact command and the cost of a second miss:

```
Your run did not report the required result field `passed:bool`.
Set it now with:  ember result set passed=true
The space cannot use this run without the field. A second miss fails
the run with reason=no_result.
```

The briefing carries the same command on its close line, so the
re-prompt is a reminder and never a new requirement.

**How the re-prompt runs.** The check happens after the run's last
round, so the process has already exited with a stop-finish tail and
`wisp continue` would refuse it with 78. The engine re-prompts with one
more `wisp run -d <run dir>`, the re-prompt text as its prompt, under
the same run lock and the same wall clock. The run row stays
non-terminal through that turn, so a daemon crash in the middle
reconciles like any other run (F5).

**One re-prompt per run, not per reason.** The engine checks all three
contracts before it re-prompts, names every miss in one message, and
takes one more turn. A second miss fails the run with the first reason
in the order `no_output`, `no_change`, `no_result`, so a run that
writes nothing is never reported as a missing field.

### 4.4 Caps, admission, settle

Evaluation runs after every atom write, in one transaction, in rule-id
order.

1. Enabled = a matching atom set with no earlier consumption, the rule
   not disabled, and the cap not reached.
2. A firing consumes its atom ids and writes a `pending` action.
3. Admission promotes pending actions in seq order while live runs < 3.
4. A cap threshold writes `rule:<id>.capped` once and stops the rule.
   The cap argument is `count(EXPR)<N`, where `<N` is the threshold and
   `N` is an integer. The wrapper is required (N23), so the threshold
   cannot read as a comparison on the atom's value; `EXPR` holds one
   atom pattern, may carry one value test, and a conjunction inside the
   count is refused at `rule add`.
5. **Settle** = no live run, no pending action, no enabled rule. The
   space writes `space.settled` on each transition into that state, with
   `red=[run ids]` naming every settled tree that is not green (§4.11),
   so a space that gave up is visible without a query.
6. An `ember steer` writes `space.steer`; the steward rule fires; the
   space leaves the settled state and settles again when the steward
   returns. Settled is not terminal.
7. No root rule layer (F8). Every space evaluates only its own rules.
8. A run that reaches a terminal state also evaluates closure: the walk
   from that run to its root writes any `agent-type:T.done` whose
   condition just became true (§4.11). Closure is part of the same
   transaction as the run-end atom, so no reader sees a done run without
   the closure it implies.

### 4.5 The briefing

The engine writes one prompt file per run; the same row feeds
`ember trigger show`.

```
# run <rid>  space <space>  agent <type>
rule: <id> v<n>
  ember rule add --event ... --run ... --require ... --in ... --cap ...
trigger: atom <seq> <subject>.<verb>  from run <rid> (<type>)
parent:  run <rid> (<type>)   |  none (root);  tree root <rid>
workdir: <space>/work/<rid>/
trace:   file syscalls recorded to <space>/logs/<rid>/trace.*
inputs:  - task:prompt v1 -> cells/task.prompt.v1
answer: run r-1a2b (designer), the trigger run's final message
  <the answer, indented; clipped to 16 KiB>
require: passed:bool  -> ember result set passed=true
cap: 1/3 (agent-type:verifier.passed)
close: ember result set passed=<true|false>
```

The run reads `EMBER_SPACE`, `EMBER_RUN`, and `EMBER_TRIGGER` from the
environment. The persona is the type's system record plus the wisp
block.

A `--resume` or `--fork` run sends the **continuation prompt** instead:
the same header with a `continues:` line naming the source run, its
state, its reason, and its exit, then the same inputs, answer, required
fields, and close line, then the rule's body verbatim. The body is the
author's instruction and the contract above it is the engine's, so a
body never repeats a field name (§4.13).

### 4.6 Query

```
ember query run:<id> [--json]
ember query runs [--where agent-type=T] [--where rule=R]
                 [--where state=live|done|failed|pending] [--json]
ember query rules|cells [--json]
```

Fields per run: id, dir, type, rule, rule version, trigger atoms,
parent, root, children, started, ended, exit, required fields, output
cells, and files (read/wrote/deleted/renamed, from §6.3). `ember query
run:<id> --tree` prints the subtree with each node's state; `--files
all` widens the file list to system reads.

### 4.7 Agent types are wisp session dirs

This replaces the round-8 `<root>/agents/<name>.md` file. An agent type
is a wisp session directory created by the user:

```
wisp new -d "$(ember space dir)/agent-types" --name verifier \
     --env-in-system-prompt -m MODEL -t THINKING \
     -s < <(wisp skill read falsifier)
```

- The directory name is the type name used by `agent-type:` and
  `--run`.
- The model and thinking are the type's, read from `wisp.run.json`.
- The persona is the type's first `wisp.jsonl` record, written by `-s`.
- A run is `wisp fork <type dir> -o <space>/runs/<rid>`, then
  `wisp run -d <space>/runs/<rid>` with the briefing as the prompt.
- No sidecar file exists in v0. `slots` and `grants` have no home until
  Y7 and Y8 land; the cap 3 is the only bound.
- Two changes are load-bearing here and neither exists yet: `wisp new
  -d DIR`, where `DIR` is the parent directory, and `wisp fork`. Both
  are already in the change list (W11, W7).
- **The environment block stops being a record (W13, round 10).** `wisp
  new` bakes `<environment>` into the first system record with an
  absolute `SESSION DIR` and the creation time (`wisp/wisp` 209–240),
  so a verbatim fork makes every run believe it lives in the type
  directory: its own `-d`, its spill path, and its brief are all wrong.
  Round 9 answered this by rewriting the block inside the copied
  `wisp.jsonl`, which the owner rejected as hacky. Round 10 removes the
  cause: the block is a **view, not a record**. `wisp new` stores the
  persona alone and writes `created`, `sessions_root`, `project_dir`,
  and `env_in_system_prompt` into `wisp.run.json`; every request
  composes `<environment>` from `wisp.run.json` and the `-d` path. A
  fork is then a plain copy of `wisp.jsonl` and `wisp.run.json` with a
  fresh `created`, and no record is rewritten. The block is identical
  across a session's runs, so the prefix cache holds; `MODEL` and
  `THINKING` follow `wisp.run.json`, so a model switch stops lying. A
  legacy record that still begins with `<environment>` has the element
  stripped and re-rendered at request time, which is the only branch
  that reads the old format. `wisp render-past` renders the same block,
  so the display matches what the model saw.

### 4.8 The steer

```
ember steer -F msg.md            # writes space.steer + steer:<n> cell
```

One rule in the space reads it:

```
ember rule add --event space.steer --run steward \
  --in steer:last --in task:prompt
```

The steward is an ordinary type with bash and the `ember` verbs. It
reads `ember query runs`, `ember query rules`, and `ember space show`,
then adds or disables rules. Its own adjustments are rule rows, so the
audit of a steer is the audit of any other step. The engine starts the
steward.

#### A steer joins

A second steer arriving while a steward is live should not start a
second steward. No flag is needed; the atom says what to do.

**A firing whose trigger atoms include `space.steer` does not start a
run when a run of the target type is live in the space.** The engine
appends one line to that run's inbox with `wisp steer -d
<space>/runs/<rid>`, records the firing as `joined <rid>`, and consumes
the atom. When no run of that type is live, the firing starts one as
usual. This is round 4's hard-wake law narrowed to the one atom that
survives: a steer is hard when idle and soft when live.

The line is the whole delivery, and it holds no path the steward must
resolve to act:

```
steer atom 57  space.steer  2026-11-17T16:44:02Z
rule steward-steer v2  (firing 61, joined)
steer:last v2            cells/steer.v2.md
task:prompt v1           cells/task.v1.md
--- message
<the steer text, verbatim>
```

A `steer:` cell's text rides the line, because a steer is short and the
steward must read it without a tool call. Every other `--in` reference
is a path, because a task or a design document is not short. Two live
runs of the target type is out of v0; the join picks the earliest
started, so the choice is deterministic and visible in the firing row.

| Steward live at the second `ember steer` | Action | Cost |
|---|---|---|
| yes | `wisp steer` the live steward, firing recorded `joined` | no new run |
| no | two-phase start | one run |

A live run is a held run lock (W2), so the test survives a daemon
restart. A run in `starting` counts as live: its row is committed in the
same transaction as `run:<id>.started`, before the spawn, so the second
steer of a burst already sees the first steer's run and joins it instead
of starting a twin. The transaction order is what closes that window,
and no timer is involved.

After the append the engine rechecks the lock: a lock that freed in the
meantime escalates to a start, and that start drains the inbox before
its own prompt, so a wrong liveness guess costs one run and never a
message. A joined steer is at-least-once; the steward names
the atom id in its reply, so a duplicate is visible in the audit.

Two consequences follow, and both are wanted:

- The join is not open to other atoms. A job, a submission, and a field
  atom always start a run, because none of them is advice.
- A run started from a **closure** atom is a new root (§4.11), so a
  steward started from `agent-type:steward.done` cannot be joined into
  the tree it just closed. It reads as the next job, which is what it is.

The steer's `--in` references are resolved at firing time, so the second
steer carries the second message's body, not the first's: `steer:last`
pins version 2 for the second firing and version 1 for the first.

#### The steward steers runs

The steward run is a model with bash, and it may steer a live worker
run. The words land in that run's inbox as data and the live run drains
them at its next round boundary; the engine is not involved and the run
keeps its lock. The steward's recipe is two commands:

```
ember query runs --where state=live --json     # run ids and dirs
wisp steer -d <space>/runs/<rid> < msg.md      # the words
```

This is an agent's act, not a routing decision, so the control plane's
determinism is untouched. It is also why the engine's rule reads "a
start, except a steer joins" and not "nothing ever injects": the engine
injects in exactly one place, and the phrasing says which.

#### The lock this brings back

Two independent writers now reach one inbox: the engine's join and a
steward's steer. `wisp steer` appends without a lock and the intake
renames the inbox, so an append that lands after the rename goes into
the consumed file and is lost (round 2, reproduced with no model; round
3, closed by a `flock`). W1's `flock` around both the append and the
intake returns to the required set for this reason alone. No `--batch`,
no `--key`: the lock is the whole change.

### 4.9 Authority and metadata

Every rule row records its creator (`owner` or `run:<id>`), its version,
and the run that disabled it, if any. `ember rule list` prints all four.
No grant is enforced. Any run may add or disable any rule in its space;
the audit names which run did it. The steward is distinguished by its
persona, not by a checked field (F6 deferred).

### 4.10 Store and recovery

- One SQLite database per space, WAL, one writer, committed before any
  action it names.
- A rule row carries `body`, `guard`, and `wallclock` besides the
  grammar fields. `target` is a type, `.parent`, `.resume`, or `.fork`.
  A run row carries `guard` and `wallclock` too, so a re-prompt repeats
  the policy, and `dir` and `workdir` may be the source run's for a
  `--resume`.
- A result row names its run: `{"run": "<rid>", "field": ..., "value":
  ..., "type": ...}`. The engine reads only rows for the run it checks,
  so two runs over one session dir cannot satisfy each other's
  contract.
- A start is two-phase: one transaction writes the run row and
  `run:<id>.started`, then the engine spawns and takes the run lock.
- On daemon start, `reconcile` walks the registry and, for every
  registered space's run rows in a non-terminal state: a free
  lock and a result row means done; a free lock and no result means
  `run:<id>.failed` with `reason=crashed`; a held lock means alive, and
  the daemon adopts the run and waits for the lock to free.
- After reconciliation the engine evaluates once. A crash therefore
  never loses a firing and never duplicates one: the firing row is
  committed with its consumed atom ids, so a replayed evaluation finds
  them consumed.

### 4.11 Trees, closure, and repairs

A run that decomposes starts more runs, so "the designer finished" is
not one run-end fact. Every run carries a parent, and two atoms close a
tree.

#### The parent is inferred

For a firing, collect the runs named by the **per-run** trigger atoms:
`run:<id>.done`, `id:<R>.done`, `me.done`, and a declared field atom such
as `agent-type:designer.ok` all name a run in their fields. The new
run's parent is the **lowest common ancestor** of those runs.

A firing with no per-run trigger atom starts a root. That covers
`space.submitted`, `space.steer`, and a closure `agent-type:T.done`,
which names the root it closes but does not belong to it.

Three consequences turn the owner's "the sending agent is the parent"
into arithmetic:

- A rule on `me.done` fires on the splitting run's own end atom, so the
  splitting run is the trigger run and the parent. A decomposition needs
  no parent flag, and nothing can declare a parent the atoms do not
  support.
- A continuation on `id:job1.done and id:job2.done` takes the lowest
  common ancestor of the two job runs, which is the run that split the
  work. The continuation is a sibling of its jobs, not their child.
- A repair on `agent-type:verifier.failed` names the failed verifier, so
  the repair is a child of the failure it answers. The audit reads as a
  repair chain instead of a flat list.

`--run .parent` names the type of the trigger run's parent, so a repair
restarts the work that owned the failure. `rule add` refuses `--run
.parent` when no conjunct names a run, because such a rule can never
fire usefully.

#### A closure atom starts a root

`agent-type:T.done` is written when a tree becomes green, so a run
started from that atom must not belong to that tree. Otherwise the tree
would wait on a start that waits on the tree, and the space would hang
with a free slot. Such a run gets parent null and begins the next job.

This is the one rule that keeps closure from deadlocking, and it is the
right reading of a decomposition: work started after a job closes is the
next job, not a child of the finished one.

#### Green, red, and repair

```
ok(r) = r.state == done and every child c: ok(c)
        or r.state == failed and some child c: ok(c) and c answers
           r's fault atom
green(r) = subtree(r) is settled and ok(r)
```

`settled(r)` means every run in the subtree is in a terminal state. A
run answers another's fault atom when its firing consumed that atom:
`run:<id>.failed` or `agent-type:<type>.failed` with that id.

A `--resume` or `--fork` run is the smallest repair: its parent is the
source run and its type is the source's, so a green continuation turns
the source's fault into a green tree, and a failed one is itself a
fault that another continuation can answer (§4.13).

The second clause is what a repair buys. A failed run stops poisoning
its tree once a rule answered its fault atom with a run that came back
green. Without the clause one repaired verification would make the root
red forever, and the design job could never be reported done, however
often it was fixed.

#### The two type atoms are asymmetric on purpose

- `agent-type:T.failed` fires per run of T, at the fault, at any depth.
  A repair cannot wait for a tree to settle, so this atom never waits.
- `agent-type:T.done` fires once per **root** run of type T, when the
  tree under that root is green. This is the owner's "the root and all
  children completed successfully". A nested designer run therefore
  writes no `agent-type:designer.done`: sequencing inside a tree uses
  `id:<R>.done` and field atoms, which are per-run and immediate, so a
  rule keyed on `.done` fires once per submitted job and not once per
  nested run of the same type.

A root tree that settles red writes no `agent-type:T.done`. The fault
atoms already fired; `space.settled` carries `red=[run ids]`, so the
owner sees what came out short without a query.

#### Cost

The engine evaluates closure when a run reaches a terminal state: it
walks from the ended run to its root and writes each closure atom whose
condition just became true. A tree of twenty runs costs twenty walks of
depth at most twenty, on a store that answers in microseconds. No
scheduler is involved and no model is consulted.

### 4.12 The input contract

One shape for every verb, so no caller has to remember which command
reads a pipe.

- A body comes from `-F FILE` or from `-F -` only; `-F -` reads stdin.
- No verb reads bare stdin, and no verb takes a body positionally.
- argv carries scalars and labels: `--event`, `--require`, `--in`,
  `--out`, `--cap`, `--id`, `--reason`, `--guard`, `--wallclock`,
  `--resume`, `--fork`, and the `FIELD=VALUE` form of `result set`.
- A missing `-F` while stdin is a pipe is a `usage` error that names
  `-F -`, so nothing is read by accident.

| Verb | Body | Why |
|---|---|---|
| `space submit` | `-F FILE` | the task text is a file, and the cell points at it |
| `steer` | `-F FILE` | the message is a file, and the atom points at it |
| `result set` | `-F FILE` (JSON) or `FIELD=VALUE` | a `str` result may be long; a bool or an int is a scalar |
| `rule add --resume`, `rule add --fork` | `-F FILE` (required) | the prompt is the rule's body; `--run` refuses a body |
| `rule add --run`, `rule disable`, `space show`, `query`, `trigger show` | none | the flags and arguments are the whole input |

`ember result set -F -` takes one JSON object with one key per declared
field. `ember result set passed=true` sets one field. Both forms write
the same rows. The briefing prints the scalar form for a bool and names
the JSON form for a `str`, so the run never has to guess.

The rule also covers the verb that reads a file twice: `--in` names a
cell, and the briefing prints the resolved path. A run never receives
content on argv, which keeps a 2 MB design document out of the process
table.

### 4.13 Three targets: run, resume, fork

A rule says where its run starts. One flag picks it: `--run TYPE`,
`--run .parent`, `--resume`, or `--fork`.

| Target | Session dir | Persona | Work dir | Prompt |
|---|---|---|---|---|
| `--run TYPE` | `<space>/runs/<rid>`, a fork of `agent-types/TYPE` | TYPE's | `<space>/work/<rid>/`, empty | the briefing (§4.5) |
| `--run .parent` | the same, of the trigger run's parent's type | that type's | the same, empty | the briefing |
| `--resume` | the trigger run's own dir, appended | the trigger run's | the trigger run's, unchanged | the continuation prompt |
| `--fork` | `<space>/runs/<rid>`, a copy of the source dir | the trigger run's | `<space>/work/<rid>/`, a copy | the continuation prompt |

- **`--resume` is one more turn of the same agent on the same job.** It
  runs `wisp run -d <the trigger run's dir>` with the prompt. It is not
  `wisp continue`: that verb reads no stdin and appends no prompt, and
  only finishes a segment a kill left open, so a continuation with a
  prompt cannot use it. The source is terminal and its run lock is
  free, so the new prompt becomes the next user record; the source row
  keeps its state, times, and report, and the new row is the epoch that
  continues it.
- **`--fork` is one more turn of a copy.** It runs `wisp fork -d
  <source dir> -o <run dir>`, then `wisp run -d <run dir>`. The copy
  keeps the source's `wisp.jsonl`, `wisp.run.json` with a fresh
  `created`, and `wisp.modelcfg`; W13 makes the copy plain. The source
  log stays frozen, and two forks of one run are two branches, which a
  resume cannot do. The work dir is copied, so the branch writes its
  own files.
- **Both inherit the source run's type**, and therefore its persona:
  the system record is inside the copied log, and no record is
  rewritten (W13). A different persona needs `--run TYPE`; the
  conversation cannot come along, only files can, through `--in`.
- **Both need a conjunct that names a run**, the same check as
  `.parent`. `rule add` also refuses a `started` conjunct, because a
  source is continued at a run end: `run:<id>.done`,
  `agent-type:<type>.failed`, a declared field atom, or
  `agent-type:T.done` is a legal trigger. A `space.steer` trigger
  therefore cannot carry `--resume` or `--fork`.
- **A firing whose source is not terminal fails `busy`**, with the
  source named, because one live run per session dir is a
  data-integrity law.

**The continuation prompt.** The engine writes it like a briefing, with
the continuation facts and the rule's body last:

```
# resume <rid>  space <space>  agent <type>
rule: <id> v<n>
  ember rule add --event ... --resume [--require ...] [--in ...] [--out ...] [--cap ...]
continues: run <src> (<type>)  <state>: <reason>  exit <code>
session: <space>/runs/<src>/  (your own records; one more turn)
workdir: <space>/work/<src>/  (the files you left)
trigger: atom <seq> <subject>.<verb>  from run <rid> (<type>)
inputs: ...
outputs: ...
require: passed:bool  -> ember result set passed=true
close: ember result set passed=<true|false>
---
<the rule's body, verbatim>
```

A `--fork` prompt names the new dirs and says they are copies of the
source's. The body is the author's instruction and the contract above
it is the engine's, so the check is satisfiable by construction.

**Results and the contract.** A resume shares the source's session dir,
so both rows would share one `results.jsonl`. A result row therefore
names its run (`{"run": "<rid>", "field": ..., "value": ...}`) and the
engine reads only rows for the run it checks; a field the source set
never satisfies the continuation. The work dir is shared by a resume
and copied by a fork, so `--out` reads and writes the job's files
unchanged. `no_change` still applies: a declared output that is
byte-identical to a committed cell version fails, so a resume declares
the outputs its next turn will write.

**Policy on the rule.** `--guard LIMIT` and `--wallclock S` are rule
flags, stored on the rule and copied to the run row, so a re-prompt
inherits both. `--guard` is passed to wisp unchanged: `70%` resolves
against the model's window in `wisp.modelcfg`, which wisp refreshes
from `WISP_LLM_MODEL_INFO_FILE`, and `150k`, `1m`, or a plain number
needs no modelcfg. The guard must leave room for the continuation: a
guard-stopped session sits at the limit, and a resume that carries a
guard stops at its first round, so the guard is the worker's (70% of
the window) and the resume rule carries none. `--wallclock 0` disables
the limit; without the flag the run takes `EMBER_WALLCLOCK` (600 s).

**Round 19 additions.**

- `--model M` and `--thinking T` are rule flags, stored on the rule and
  copied to the run row. Both pass to `wisp fork -m/-t`, so they cover
  every target that forks a dir: `--run TYPE`, `--run .parent`, and
  `--fork`. `--resume` forks nothing and refuses both, because the
  session's pair is in the `wisp.run.json` the resume keeps. This is
  how a reviewer runs on another model than the worker, and how a
  branch carries Q17's fallback pair.
- `--out` accepts `session-file:` and `resource:` only (N14). Both bind
  a cell version; the difference is the path the briefing prints, and a
  `resource:` path is space-scoped, so two rules can share one file
  (`resource:review-latest.md` is the reviewer's stable address).
- A wallclock stop is a failure, period (N13): `finish_run` tests exit
  124 before the contract, so a run that wrote every output and every
  field still fails `wallclock`. The contract check applies to exit 0
  and to nothing else.
- The fault atom carries its reason as its value (N19):
  `agent-type:T.failed` and `run:<id>.failed` both get
  `value=reason`, so a rule selects one reason with
  `--event agent-type:T.failed=guard`, and the cap counts one reason
  with `--cap 'count(agent-type:T.failed=guard)<3'`. A rule with no
  comparison still matches every reason.

**Tree.** A resume or fork run's parent is the trigger run, so it
answers that run's fault atom and a green continuation turns the failed
run's tree green. A resume of a `done` run is a child of that run, so a
failed resume turns that tree red. A failed resume writes
`agent-type:T.failed` again with its own run id and retriggers the rule
that started it, so a rescue rule carries a cap.

### 4.14 Agents and rules: the named contract (round 20, proposed)

**The split.** An agent row is a named run contract. `ember agent add
NAME` takes the whole run shape: `--type T`, `--require FIELD:TYPE...`,
`--in CELL...`, `--out CELL...`, `--guard LIMIT`, `--wallclock S`,
`--model M`, `--thinking T`, `--trace none`, and a briefing body through
`-F FILE`. A rule row keeps only the wiring: `--event`, the target,
`--cap`, `--id`. `--run agent:NAME` starts the agent; `--resume
agent:NAME` and `--fork agent:NAME` continue a source run under the
agent's contract; a rule-level `--in` list **extends** the agent's
inputs — the agent's entries first, an exact repeat dropped, the merged
list on the run row — and no other flag can be overridden on the rule — a different
contract is a different agent.

**Why.** Every `--run TYPE` rule row today duplicates the contract, and
every continuation rule re-declares it by hand; that duplication is what
made the round-19 recipe hard to read. The split makes inheritance
visible: `--run agent:pickup --in session-file:handoff.md` inherits the
type, the required fields, the outputs, the guard, the wallclock, and
the model pair, and only the inputs differ. `.parent` keeps its meaning
(the trigger run's parent's type) but leaves the recipes, because the
agent names the type outright; the tree is unchanged either way, since
both forms parent the new run on the trigger run.

**The body.** `--run agent:X` takes no `-F`: the agent row carries the
briefing. `--resume agent:X` and `--fork agent:X` take their body from
the agent row too, so the distill prompt lives on the distiller agent.
This is the round-17 resource wish in a better form than either round-17
(`--distill RESOURCE` plus a resource store) or round 18 (the body on
the rule row): the prompt is named, versioned by its row, and referenced
by every rule that needs it. N15's settlement (no resource store) stands;
`resource:` remains an output category only — a stable space-scoped path
for an artifact others read by fixed name, never an input mechanism.

**Resume and fork over an agent.** The type comes from the source run,
so the agent's `--type` is ignored on `--resume` and `--fork`; a
distiller agent simply omits it. `--model` and `--thinking` still apply
only to targets that fork a dir, and `--resume` still refuses both. A
distiller agent carries no `--guard` (N17: the resume needs headroom)
and usually no `--in` (the distill turn works from the conversation the
session already holds).

**Storage and identity.** An `agents` table (name, version, type,
required, inputs, outputs, guard, wallclock, model, thinking, trace,
body, creator, created); run rows gain `agent` and `agent_version`
columns, so a failure report names the contract it checked. Agent rows
are immutable; a re-add under the same name writes the next version and
the name resolves to the latest, exactly as cells do. Bare `--run TYPE`
stays as the anonymous form — the rule carries the flags directly — so
a one-off rule needs no named agent, and every existing rule row keeps
its meaning. Under the split, N1 settles: the agent row is the shared
contract, and the type carries no defaults.

**Two recipes, the owner's shapes.** Both live in one space with two
agent types (`worker`, `reviewer`) made as §4.7 describes. Recipe A is
the review loop; recipe B is the distill loop. They are separate rule
sets over the same agent rows — mixing them in one space is what made
the round-19 recipe hard to read.

Recipe A — the worker and the reviewer:

```
ember agent add pickup --type worker \
  --require ready:bool --in task:prompt \
  --out session-file:answer.md \
  --guard 70% --wallclock 1800

ember agent add review --type reviewer \
  --require approved:bool --in task:prompt --in .out \
  --out session-file:review.md --wallclock 1800

ember rule add --event space.submitted --run agent:pickup

ember rule add --id review \
  --event 'agent-type:worker.ready or agent-type:worker.failed' \
  --run agent:review

ember rule add --id loop \
  --event 'agent-type:reviewer.approved=false' \
  --run agent:pickup --in .out \
  --cap 'count(agent-type:reviewer.approved)<4'
```

- `pickup` fires on the submit; the worker reads the task cell, writes
  `answer.md`, sets `ready=true`.
- `review` fires on the worker's finish, success or failure. On success
  `.out` is the answer version. On failure `.out` has no version from
  this run, and `briefing_of` today falls back to the latest cell version,
  so it may hand the reviewer a **stale** answer from an earlier loop
  round; the design already says `.out` is the triggering run's output
  version, and a `cells` row records the writing run, so the split
  resolves `.out` against the trigger run and prints `(no output version
  yet)` instead. Either way the reviewer persona must branch on the
  trigger line:
  a `failed` trigger names the run id, and `ember query run:<id>`
  prints the whole failure report (reason, last words, fields set,
  workdir). The persona reviews that instead of an answer file.
- `loop` fires on a no-go and restarts the worker with the task and the
  review as inputs. The cap counts every `agent-type:reviewer.approved`
  atom, true or false, and the `count(...)` wrapper (N23) says so: the
  first review plus three restarts is four, so `<4` grants exactly three
  loops; the fourth no-go writes
  `rule:loop.capped` and the space settles.
- The verdict is the `agent-type:reviewer.approved` atom, never the
  closure: `agent-type:worker.done` means the tree finished, and a
  rejected job still closes green (round 16).

Today, without the disjunction (N21), `review` is two rules with the
same agent — `--event agent-type:worker.ready` and
`--event agent-type:worker.failed` — and exactly one of them fires per
worker run, so the behavior is identical.

Recipe B — the distill loop:

```
ember agent add pickup --type worker \
  --require ready:bool --in task:prompt \
  --out session-file:answer.md \
  --guard 70% --wallclock 1800

ember agent add distill \
  --require handoff:bool --out session-file:handoff.md \
  -F distill.md

ember rule add --event space.submitted --run agent:pickup

ember rule add --id rescue --event agent-type:worker.failed \
  --resume agent:distill \
  --cap 'count(agent-type:worker.failed)<4'

ember rule add --id continue \
  --event 'agent-type:worker.handoff=true' \
  --run agent:pickup --in session-file:handoff.md
```

- The worker stops on the wallclock (exit 124, reason `wallclock`) or on
  the guard (exit 75, reason `guard`); both write
  `agent-type:worker.failed` with the reason as the value, and the bare
  event matches every reason. To take only the two caps, narrow the
  event to `'agent-type:worker.failed=wallclock or
  agent-type:worker.failed=guard'` and cap on
  `count(...)` over the same expression (N23).
- `rescue` resumes the failed run in its own session dir with the
  distill prompt as the agent body and no guard. The distill turn
  writes `handoff.md` into the shared work dir and sets `handoff=true`;
  the resume run is a child of the failed run and answers its fault
  atom.
- `continue` starts a fresh worker run of the same agent: type,
  required fields, outputs, guard, wallclock all inherited, only the
  inputs differ (task plus handoff). Its parent is the resume run, so
  the tree records failure → distill → continuation.
- The budget counts worker failures, not handoffs: every rescue firing
  needs a fresh `agent-type:worker.failed` atom and every cycle adds
  exactly one — the pickup's stop, each continuation's stop, or a
  distill that itself fails (a resume inherits the worker type and
  writes the same fault atom). The rule fires at counts 1, 2, and 3 and
  blocks at 4: three distill-and-restart cycles, whichever side fails.
  The round-19 cap `handoff<3` counts only successful distills, so a
  failing distill retriggers rescue without ever moving the counter;
  that cap is wrong and is dropped.
- The whole job succeeds when a worker succeeds: any green continuation
  heals the chain, because every failed run in it has an answering
  resume child; the root turns green and `agent-type:worker.done`
  fires. If all three cycles fail, `rule:rescue.capped` is written and
  the root stays red.

### 4.15 Human gates (round 24, proposed)

The engine lacks one party: the human. A rule can chain runs, but no
rule can stop and ask. The owner's static shape: a rule declares the
fields a human must return (`--require-human answer:string
--require-human approved:bool`), and a loop rule keys on the approved
bool. Dynamic asking — a run deciding mid-flight to open a question —
is deferred by the owner; only rule-authored gates are designed here.

Four facts from the code bound every design:

- `maybe_settle` counts `NONTERMINAL` runs and `admit` counts
  `LIVE_STATES` runs, and the two lists already split the way a
  waiting human needs: a state in `NONTERMINAL` only blocks settlement
  and closure and holds no concurrency slot.
- `tree_settled` and `tree_ok` read the `runs` table only, so anything
  that is not a run row is invisible to closure: a gate outside
  `runs` needs new tree functions, or the root closes before the
  human answers.
- `finish_success` turns declared fields into atoms keyed
  `agent-type:<type>.<field>`, and events, caps, and type-strict
  matching already speak that subject.
- `wisp_lock_free` treats a missing dir as a free lock and
  `reconcile` crash-fails every non-terminal row whose lock is free,
  so a waiting row with no dir and no process must be excluded from
  `reconcile` or it dies at the next daemon start.

**Design A — the gate row (the owner's shape).** A rule may take
`--require-human FIELD:TYPE ...` instead of a `--run` target: the
firing opens a gate, not a run. A `gates` table holds the row — id,
rule and version, trigger atoms, parent and root (what a run of this
rule would get), the rule's body as the question, the field
declaration, `state open|answered`, and times. The verb pair is
`ember gate list`, which prints the open gates with their question
and trigger, and `ember gate answer GID --field approved=true -F
answer.md`, which type-checks the fields against the declaration
(the `parse_require` types), stores the answer text, marks the row
answered, and writes the atoms: subject `gate:<rule-id>`, verb the
field name, value the field — `gate:confirm.answer`,
`gate:confirm.approved=true` — with `fields.gate` naming the row. The
rule wants `--id`, because the atom subject names it. The loop rule
is `--event gate:confirm.approved=false --run agent:pickup --cap
'count(gate:confirm.approved)<4'`. Settlement and closure grow one
clause each — an open gate counts as open work in `maybe_settle`, and
a root's tree is neither settled nor green while a gate under it is
open — which means `tree_settled` and `tree_ok` grow a gate branch,
because they read runs only today. The briefing grows a gate variant
of the answer block: `answer: gate <gid> (confirm)` plus the answer
text. Cost: one table, two verbs, one flag, one atom subject, and
amendments to settle, closure, trees, and the briefing. The gate is a
first-class row kind with its own laws.

**Design B — the human as a manual agent type.** The engine already
has the concept "a party that must return typed fields before its
tree closes"; it is called a run. Design B makes the human one. The
rule's target is `--run human:LABEL` — `human:` reserves the
namespace and LABEL is a pseudo-type with no directory under
`agent-types/` — and the rule keeps the flags it already has:

```
ember rule add --id confirm \
  --event agent-type:reviewer.passed \
  --run human:confirm \
  --require answer:str --require approved:bool \
  --in task:prompt -F question.md
```

The firing creates a run row as usual — type `confirm`, `mode
manual`, parent and root from `infer_parent` — but `admit` forks no
dir and spawns nothing: the row sits in state `waiting`, a member of
`NONTERMINAL` and not of `LIVE_STATES`, so it blocks settlement and
closure exactly as a live run does, holds no slot, and has no
wallclock, guard, or trace. The question is the rule body stored on
the row's briefing; `ember gate list` (or `ember query runs`) shows
it. The human answers with `ember answer RID --field approved=true -F
answer.md`: the engine type-checks, writes the result rows, stores
the answer text on the row, and calls the unmodified `finish_success`,
which writes `agent-type:confirm.approved=true` and `run:RID.done`.
The loop rule is the existing reviewer loop with a human in the
reviewer's chair:

```
ember rule add --event agent-type:confirm.approved=false \
  --run agent:pickup --cap 'count(agent-type:confirm.approved)<4'
```

Under N20 the shape is cleaner still: `ember agent add confirm
--human --require answer:str --require approved:bool -F
question.md` names the contract once and every rule references
`agent:confirm`. Guards, not laws: `admit` skips `mode manual`;
`reconcile` skips it too (a waiting row has no dir, and a free lock
on a missing dir would crash-fail it at daemon start); `answer_of`
reads the stored answer text for a manual row instead of
`wisp.jsonl`, so the next briefing's answer block works. Cost: one
target spelling, one state, one verb, four guards. Trees, closure,
caps, and atoms change not at all.

**Landed in round 28 (N25 b), in `ember/ember`.** The surface is as
designed, with three spelling facts: the declared string type is
`str` (`--require note:str`), the question is read with `ember query
run:RID` (the `question:` block) or `ember trigger show`, since
`ember gate list` was never built, and `ember answer RID --field
F=V... -F FILE` is the verb. `rule add` refuses `--guard`,
`--wallclock`, `--model`, and `--thinking` on a `human:` target and
stores `trace none`; `NONTERMINAL` gains `waiting` (a state that is
open work for `maybe_settle` and invisible to `admit` and
`live_runs_all`); `reconcile_space` skips both the state `waiting`
and `mode manual`; `ember result set` refuses a manual run; the
runs table gains an `answer` column that `answer_of_row` reads for
manual rows; and `apply_answer` calls the unmodified
`finish_success` then pumps, closes, and settles.

**Landed in round 30 (N26 a), in `ember/ember`.** `ember answer RID
--dismiss` fails a waiting gate with no answer: it takes no `--field`
and no `-F`, calls `finish_failed` with `reason=dismissed`, and pumps,
closes, and settles, so `run:RID.failed` and
`agent-type:LABEL.failed` carry `value=dismissed` (a rule may select
the reason: `--event agent-type:LABEL.failed=dismissed`), the root's
tree goes red, and the space settles instead of hanging. A dismissal
of a done gate, a model run, or a dismissal carrying fields is
refused with exit 2.

**Design C — the atom-only gate.** No row waits. A rule with `--gate
NAME` fires like any rule but its target is nothing: the engine
writes one atom, `gate:NAME.asked` (value the clipped question,
fields the trigger run), stores the full question in a cell, and
stops. The human answers with `ember gate answer NAME --field
approved=true -F answer.md`, which writes `gate:NAME.approved=true`
and `gate:NAME.answer`; loop rules key on those. Nothing blocks: the
space settles with the question open, the root's closure fires before
the human answers, and the pairing between a question and its answer
is the NAME alone — two jobs under one gate kind cross-contaminate,
because events test subject, verb, and value, never `fields`. Making
settlement wait would reintroduce state by another name. C is honest
only for a global, single-instance question — "may this space keep
going" — which is Q31's hard-gate flavor, not per-job review.

**Comparison.** B is recommended. A is the owner's syntax made real
and the most explicit about who answers what, but its gates are
invisible to the run-shaped tree, so closure, settlement, and repair
each grow a gate branch, and `--require-human` duplicates
`--require` beside it. B gets the identical static shape — declared
fields, a loop rule on the bool — through the existing run row, and
the human differs from a worker on exactly one axis: the engine
spawns nothing. The waiting semantics are free (`NONTERMINAL`
without `LIVE_STATES`), the tree semantics are free (a manual run is
a run), the atoms are free (`agent-type:LABEL.FIELD`), and the loop
rule is the recipe §4.14 already runs. A's one genuine advantage —
the question is delivered to a human, so no briefing is composed for
a model — B keeps by storing the body on the row and printing it in
`ember gate list`. C is rejected for per-job gates and stays a note
on Q31.

Two gaps common to A and B: a gate nobody answers kept the space
unsettled forever, until the dismissal verb landed (N26, round 30);
and the
socket is 0700, so "the human" is whoever owns the space directory —
a named approver is out of scope. Dynamic asking stays deferred per
the owner.

## 5. The examples, re-expanded

### 5.1 The three rules

| # | Row | Notes |
|---|---|---|
| R1 | `--event space.submitted --run designer --require ok:bool --in task:prompt --out session-file:design.md` | fires once; the designer must report `ok` |
| R2 | `--event agent-type:designer.ok --run verifier --require passed:bool --in .out --out session-file:design-verification.md --cap agent-type:verifier.passed<3` | fires per designer run; the cap counts green verifications in the space |
| R3 | `--event agent-type:verifier.failed --run .parent --require ok:bool --in session-file:design.md --in .out --in task:prompt --out session-file:design.md` | restarts the designer; `design.md` existed, so the change check applies and an unedited design fails `no_change` |

Nothing consumes `agent-type:verifier.passed`, so a green verification
settles the space. `ember space show` says so.

The trees follow the atoms: d1 is a root; R2's verifier is a child of
d1; R3's repair is a child of the verifier it answers. So
`agent-type:designer.done` fires once, when d1's whole tree is green,
whether or not it took a repair. R2 fires again for d2's field atom,
because a declared field is per-run.

### 5.2 The decomposition

```
ember rule add --id job1 --event me.done --run worker \
  --require ok:bool --in session-file:job1.md --out session-file:job1-result.md
ember rule add --id job2 --event me.done --run worker \
  --require ok:bool --in session-file:job2.md --out session-file:job2-result.md
ember rule add --event 'id:job1.done and id:job2.done' --run worker \
  --require ok:bool --in session-file:job-cont.md \
  --in session-file:job1-result.md --in session-file:job2-result.md
```

`me.done` is `run:<S>.done`, the end of the splitting run, and both job
rules consume it in their own right. `id:job1.done` names the run that
rule job1 started; it is a run-end fact, not a field.

The parent needs no flag. Both job rules take S as the parent, because
S's own end atom is the trigger. The continuation takes the lowest
common ancestor of the two job runs, which is S, so it is a sibling of
its jobs and S's tree is green only when all three came back. A
continuation keyed on `agent-type:worker.done` would instead become a
new root (§4.11), which is the correct reading: the job was already
closed.

### 5.3 The generic verifier, per space

The root library is out of v0, so a generic verifier is copied into each
space by the submit step or by the steward:

```
ember rule add --event agent-type:worker.ok --run verifier \
  --require passed:bool --in .out --out session-file:verification.md
```

`{trigger}` is out (Y3), so every verification binds a new version of
one name. The firing row pins the version it read, so the audit stays
exact. N3 settles the same way: a rule that needs two distinct outputs
declares two cells, and the run that wants a per-run name declares one
cell per rule.

### 5.4 The user steer

```
ember steer -F reshape.md
ember rule add --event space.steer --run steward --in steer:last --in task:prompt
```

### 5.5 Atom sequence, designer/verifier

```
t0  space.submitted
t1  R1 fires                 start designer (task:prompt -> design v1)
t2  run:d1.started
t3  run:d1.done              + agent-type:designer.ok
t4  R2 fires (1 of 3)        start verifier (design v1 -> verification v1)
t5  run:v1.failed            + agent-type:verifier.failed
t6  R3 fires                 start designer (design v1, verification v1 -> design v2)
t7  run:d2.done              + agent-type:designer.ok
t8  R2 fires (2 of 3)        start verifier (design v2 -> verification v2)
t9  agent-type:verifier.passed
t10 settle under d1          every run terminal, v1 repaired by d2
t11 agent-type:designer.done written for the root d1
t12 space.settled            no live run, no pending action, no enabled rule
```

The parent chain is d1 → v1 → d2 → v2. `v1` is red on its own and green
in the tree, because d2 answers v1's fault atom and d2 came back green.
The closure atom is written once, at t11, and not at t3: d1's tree was
still open when the designer process ended.

## 6. File-change capture (F7)

Round 10 settles this section. Round 9 read the owner's F7 as "isolate
the run and diff its directory"; round 10 restated the requirement as
"watch the syscalls", because a directory only shows writes the engine
already owns. §6.1 is the requirement, §6.2 is the candidate table as
round 9 measured it, and §6.3 is the pick and its measurements.

### 6.1 What precision means

Three properties, and a candidate must hold all three:

1. exact path, including additions, deletions, and renames, for a run
   that writes outside the directory the engine gave it;
2. a per-run attribution that cannot blur when two runs are live (cap 3);
3. no privilege the daemon does not have (uid 457802145, no sudo).

### 6.2 Candidates, measured in round 9

| Candidate | Adds/removes/modifies | Attribution under two live runs | Privilege | Verdict |
|---|---|---|---|---|
| namespaces plus overlayfs upperdir | exact | exact, per mount | `unshare -Ur -m` fails `EPERM` writing uid_map; `bwrap` fails "setting up uid map: Permission denied" | **unavailable on this host** |
| fanotify with `FAN_REPORT_PIDFD` | exact | exact, carries pid | needs `CAP_SYS_ADMIN` to mark the mount | out |
| bpftrace on `sys_enter_openat` / `unlink` | exact | exact, carries pid | needs root | out |
| inotify / fswatch | exact events | no pid in the event | none | blurs; not installed |
| nono `rollback show --json` | net diff | measured blur: two sessions on one path report each other's writes; `.git` excluded; no session id on exit | none | kept for sandbox and rollback, not for the change list |
| git worktree per run, `git diff --cached --name-status` | exact `A`/`M`/`D` | exact, one worktree and one index per run | none, needs a repo | viable when the space is a repo; costs a branch and a commit per run |
| jj working copy per run | exact | exact | none | same trade as git |
| `strace -ff -y` around the run, curated syscall set | exact syscall ops, paths resolved, reads included | exact, one trace file per pid | none, measured | **pick in round 10**, §6.3; misses a write through a pre-existing mmap |
| stdlib snapshot diff of a per-run directory | exact net `+`/`~`/`-` **inside that directory only** | exact by construction | none | **dropped as the recorder in round 10**: blind to source edits and to reads of `~/.config` |

Measured on this host: `unshare` and `bwrap` both refuse to map a uid;
`strace -ff -y` reports `openat(AT_FDCWD</tmp/f7s>, "mod.txt",
O_WRONLY|O_CREAT|O_APPEND, 0666) = 3</tmp/f7s/mod.txt>` and
`unlinkat(AT_FDCWD</tmp/f7s>, "gone.txt", 0)`, so both the operation and
the resolved path are present. A Python snapshot diff over a 200-file
tree reports the exact set `del.txt -`, `mod.txt ~ +10`, `new.txt +` and
costs 16.5 ms for two walks.

### 6.3 The pick: strace around every run

The snapshot diff is dropped as the recorder. It is exact only inside a
directory the engine already owns, so it cannot see what the owner
named: a worker editing source, a research agent reading `~/.config`.
Round 10 makes the syscall tracer the recorder; the work dir stays for a
different job.

#### The mechanism

The engine wraps its own spawn:

```
strace -ff -y -s 0 -e trace=<curated> -o <space>/logs/<rid>/trace \
  wisp run -d <space>/runs/<rid> --no-stream
```

- `-ff` writes one trace file per pid, so every process the run spawns
  is traced; `-y` resolves each path argument to an absolute path
  wherever the kernel carries an fd.
- `-s 0` drops data payloads: the trace records paths and operations,
  never file content.
- `-o <prefix>` gives one directory per run, so attribution is the
  directory. Two live runs cannot blur because their prefixes differ.
- The child's exit code passes through unchanged, so 75, 76, 78, and 124
  still mean what W4 says.
- No privilege: the engine traces its own child, so the yama ptrace
  policy does not apply and no capability is needed.

#### The curated syscall set

`%file` also traces `stat`, `access`, and `readlink`, and a Python tool
call walks thousands of those through its import path. The engine names
the calls it needs:

```
open openat openat2 creat unlink unlinkat rename renameat renameat2
mkdir mkdirat rmdir link linkat symlink symlinkat truncate ftruncate
chmod fchmod fchmodat getcwd chdir
```

Measured on this host, one `python3 -c pass`:

| Trace | Time added | Raw trace | Lines |
|---|---|---|---|
| `-e trace=%file` | 0.51 s | 2.3 MB | 11.8k |
| curated set | 0.32 s | 0.66 MB | 455 |

The floor is 9 ms per traced process, measured on `/bin/true`, and a
trivial two-command tool call traced 18 pids. A tool-heavy run therefore
pays roughly a third of a second per tool call and about 0.6 MB of raw
trace. Both are acceptable because the trace is deleted after the parse
(below), and a rule may pass `--trace none` for a type that must not pay
it.

#### The parsed rows

The engine classifies each recorded call and keeps one row per
`(run, op, path)`:

| Op | Syscalls | What it means |
|---|---|---|
| `read` | `open`, `openat`, `openat2` with `O_RDONLY` | the run read this file, including `~/.config` |
| `write` | the same with `O_WRONLY`, `O_RDWR`, `O_CREAT`, `O_TRUNC`, `O_APPEND` | the run wrote or created this file |
| `delete` | `unlink`, `unlinkat`, `rmdir` | the run removed this path |
| `rename` | `rename`, `renameat`, `renameat2` | both paths, old and new |
| `meta` | `mkdir`, `link`, `symlink`, `truncate`, `chmod` | a directory, a link, or a mode change |

A failed call is kept: a probe of a missing config file is a fact.

#### Resolution and the one measured gap

`-y` gives `openat(AT_FDCWD</abs/cwd>, "x", ...) = 3</abs/x>`, so both
the operation and the resolved path are present, for absolute and
relative opens alike. One gap is measured and handled: `unlink("gone")`
carries no dirfd, so a relative delete has only a relative path. The
parser tracks each pid's working directory from `chdir` and `getcwd`
returns, which is why the curated set includes both. A path that still
does not resolve keeps its raw form and is marked `unresolved`; the raw
trace is the fallback for that row.

#### Retention

The raw trace is deleted after the parse, unless the run failed; a failed
run keeps its trace for one audit. The parsed rows are space data.
`ember query run:<id>` prints them, and the default view collapses
system noise: reads under `/usr`, `/lib`, `/proc`, `/sys`, and `/dev`
are counted and shown only with `--files all`. Writes, deletes, and
renames are always shown.

#### What it does not see

A write through an mmap set up before the trace, a copy through
`sendfile` or `splice`, and any work inside `io_uring` produce no path
syscall. The tracer records; it does not prevent. A space that must
prevent a write keeps nono, with a write grant equal to the work dir.

#### What the work dir is still for

Each run still works in `<space>/work/<rid>/`, because declared outputs
must be unambiguous and F3's change check compares a declared output
with the previous cell version. Isolation is now a convention for
outputs, not the mechanism of attribution: the tracer supplies
attribution, and isolation supplies a clean place to write.

## 7. Consequences: what ember needs from wisp now

| # | Change | Status under round 10 |
|---|---|---|
| W1 | steer lock (`flock` on the append and the intake) | **required again in round 10**, lock only: two writers reach one inbox, the engine's joined steer and a steward's `wisp steer` (§4.8). No `--batch`, no `--key` |
| W2 | run lock | **required**: the liveness record, and the test that decides join versus start |
| W4 | exit table plus machine line | **required**: 75 and 78 are engine signals |
| W5 | `status --json` | **required**, minus `committed_keys` |
| W7 | `wisp fork` | **required**: a run is a fork of the type dir. Round 10 removes the record rewrite: `fork` copies `wisp.jsonl` and `wisp.run.json`, sets `created`, and touches no record (§4.7) |
| W10 | `--no-stream` | required for every run, and for the strace wrapper |
| W11 | `wisp new -d DIR` | **required**: a type dir lives in the space; `DIR` is the parent directory |
| W12 | `--wallclock` | required |
| W13 | request-time `<environment>` | **new in round 10, required**: the block is a view rendered from `wisp.run.json` and `-d`, never a record. This is what makes W7 a plain copy (§4.7) |
| W3, W6, W8, W9, W0 | dropped, dead, or withdrawn | unchanged |

Round 12 lands all nine. Round 18 adds none: the three targets reuse
`wisp run -d`, `wisp fork -d -o`, `--wallclock`, and the existing
`--context-guard`; the work is ember's alone.

## 8. Open questions

| # | Question | Options | Rec |
|---|---|---|---|
| N1 | `--require` is a rule flag, so two rules over one type can demand different fields. Does the type carry a default field set that a rule may extend? | (a) rule only, one type may report different fields per rule; (b) type declares a default, a rule may add; (c) type only | **subsumed by N20 (round 20)**: the agent row is the shared contract; the type carries no defaults |
| N2 | What is the cap's counter scope? F1's expression has no scope word. | (a) the whole space; (b) per `--id` ancestor; (c) per rule | a |
| N3 | Is a fixed cell name acceptable now that `{trigger}` is out? A per-run output needs a distinct cell per rule. | (a) yes, distinct cells per rule; (b) return `{trigger}`; (c) the agent picks the name | a |
| N4 | Is `agent-type:T.done` root-scoped, firing once per submitted job (§4.11), or does every run of T whose subtree is green fire it? | (a) root only; (b) any run of T | a: a decomposition already sequences with `id:`, and a nested `.done` would double-fire a rule keyed on the type |
| N5 | Raw trace retention: delete after the parse on success, keep a fixed window, or keep everything? | (a) delete on success, keep a failed run's trace; (b) seven days; (c) keep all | a, at 0.6 MB per tool call |
| N6 | Is a steer's join kind-scoped (any `space.steer` rule joins a live target) or steward-only? | (a) kind-scoped, which needs no flag; (b) steward-only, which needs a type special case in the engine | a: the atom's subject decides, and the engine never has to know a steward from a worker |
| Q7 | Account token budget per minute | unchanged | b, then a |
| Q15 | `ember tail` | unchanged | a |
| Q17 | Router contract and fallback shape | unchanged | a |
| Q18 | Which wall clock wins with several pending atoms | unchanged | a |
| Q19 | Distill in the same session | unchanged | a |
| Q21 | `fork` destination | **settles as (a) with a named dir**: `<space>/runs/<rid>` | a |
| Q29 | Rule safety caps | **settles as (b)**: the cap expression only; no `rules.max`, no `firings.max`, no subtree rule | b |
| Q31 | Is the review-before-commit gate a rule or an engine gate? | unchanged; sharper, because any run may disable a rule | c |
| Q33 | Claim seam for cross-space exclusivity | unchanged, deferred | a |
| N20 | Split rules into agents and rules: `ember agent add NAME` carries type, require, in, out, guard, wallclock, model, thinking, trace, and body; a rule keeps event, target, cap; `--run/--resume/--fork agent:NAME`; a rule-level `--in` extends the agent's inputs (exact repeats dropped) | (a) yes, as §4.14; (b) keep the flags on the rule and make `.parent` inherit them; (c) agents without bodies, body stays on resume/fork rules | a |
| N21 | Disjunction in `--event`: `A or B`, each side a conjunction, one firing from either side | (a) yes, ` or ` at the top level, and `--cap` may take it too; (b) no, two rules over one agent; (c) a `--event-any` flag | a |
| N22 | Is the failure report a first-class input? | (a) no for v0: the persona runs `ember query run:<id>`, which prints the stored report; (b) a `.report` backreference input beside `.out`; (c) the engine writes the report into the failed run's work dir | a |
| N23 | The cap spelling: `--cap EXPR<N` glues the threshold to an atom expression, so `agent-type:reviewer.approved<4` reads as a value test on a bool field and `agent-type:worker.failed<4` reads as a numeric test on the reason string. | (a) a required `count(...)` wrapper: `--cap 'count(EXPR)<N'`, and the bare form is refused; (b) keep `EXPR<N` and document that `N` is a count; (c) a separate `--max N` beside `--cap EXPR`; (d) an engine-written `agent-type:T.ran` counter atom | **settles in round 22 as (a)**, and it is code: `parse_cap` requires the wrapper, the bare form exits 2, and the two grammars split cleanly — `--event agent-type:reviewer.defects>5` tests one atom's value, `count(agent-type:reviewer.approved=false)<4` counts atoms whose value passes such a test. (d) stores a derived fact, drifts when a counter write is lost, and counts starts rather than finished runs. |
| N24 | Is `--out` needed at all, given that a run already answers in its final message? | (a) drop it: the engine reads the triggering run's final assistant text and injects it into the next briefing, keeping `--require` as the typed contract; (b) keep `--out` for files and add the answer beside it; (c) keep `--out` and require a file from every run | **settles in round 23 as (a)**, and it is code: `--out` is gone, `no_output` and `no_change` are gone, a `.` reference in `--in` is refused, the answer rides every firing that names a run, and `no_response` replaces the file-existence gate. (b) keeps two channels for one fact and keeps the stale `.out` resolution; (c) makes every run write a file that the answer already carries. |
| N25 | The static human gate: a rule stops and asks a human for typed fields before the work continues. | (a) design A, the owner's `--require-human` on the rule, a `gates` table, `ember gate answer`, atoms `gate:<rule>.FIELD`, and gate branches in settle, closure, and trees (§4.15 A); (b) design B, the human as a manual agent type: `--run human:LABEL` (under N20, `ember agent add NAME --human`), state `waiting`, `ember answer`, atoms `agent-type:LABEL.FIELD`, guards on `admit`, `reconcile`, and `answer_of` (§4.15 B); (c) design C, `--gate NAME` writing asked/answer atoms with no waiting state (§4.15 C) | b |
| N26 | A gate nobody answers blocks settlement forever. | (a) `ember answer RID --dismiss` fails the row with `reason=dismissed`, writing the fault atom a rule may consume; (b) `--gate-timeout S` on the rule fails the gate at a deadline; (c) both | **settles in round 30 as (a)**, and it is code: the dismissal rides `apply_answer`, calls `finish_failed(reason=dismissed)`, and the fault atoms carry the value a rule selects; (b) adds a deadline the engine must arm and poll for a row with no process. |
| N27 | The daemon's scope: one global hearth or one hearth per space? | (a) one global hearth; (b) per-space hearths plus a crash-safe global slot ledger; (c) per-space hearths and per-space caps | **settles in round 27 as (a)**, and it is code: one daemon at `EMBER_STATE_ROOT`, the space rides the request payload, the cap counts live runs across every space with round-robin admission, `reconcile` walks the registry at start, and a per-space pause flag holds one space's admission. |
| N28 | The store's scope under a global hearth: one SQLite file for all spaces, or one DB per space? | (a) one DB; (b) one DB per space with `ATTACH` for the UI; (c) per-space files plus a daemon-written rollup metrics DB | **settles in round 27 as (a)**, and it is code: a `spaces` registry table, a space binding (the directory path) on every table and fixed meta key, global `atoms.seq` and globally unique run ids with per-space queries filtering by the binding, `ember space export` for portability, `ember space list`, and content left per space on disk. (b) gives no global seq and no one-file listing; (c) is a derived copy that drifts, the fault that killed N23 (d). |
| N29 | Is `hearth` still a required name, and can the daemon verb be `ember space start`? A space is data (a registered directory: rules, atoms, runs, cells, work dirs); the hearth is the only process (one daemon per user at `EMBER_STATE_ROOT`: pump, admit, poll, reconcile, the one-writer law). `ember hearth start` names the process and takes no space; `space init` registers data and `space pause`/`unpause` gates one space's admission | (a) keep `ember hearth start`: the round-2 metaphor still fits — one hearth tending every ember — and the state-root files (`hearth.sock`, `hearth.pid`, `hearth.log`) carry the name; (b) rename to `ember daemon start`: honest and plain, a pure alias with no semantic change; (c) `ember space start`: names the wrong thing, because a space is never started and one daemon serves every space, so no verb can start one space's process; (d) hide the daemon: the CLI auto-starts the hearth on the first mutating verb, which breaks the stateless-client law and adds a spawn-from-CLI mechanism | **settles in round 29 as (b)**, and it is code: the verb is `ember daemon start|stop|status`, the hidden `_serve` action spawns `daemon _serve`, the state-root files are `ember.db`, `ember.sock`, `ember.pid`, and `ember.log`, `Hearth` is `Daemon`, and `daemon start` retires a pre-rename daemon that holds the same database instead of letting a second writer open it. (a) keeps two names for one process and names three files after a role; (c) names a start that does not exist |
| Q43 | Steward concurrency | **settles in round 10 as "a steer joins"**: a second steer appends to the live steward, so no per-type slot is needed and Y7's slots stay deferred for other types | settled |

Round 18 settles the continuation questions N11, N12, N15, N16, and
N17 in `ticket.md` and adds N18 and N19 there; round 19 settles N13, N14,
N18, and N19 there too. Round 20 adds N20, N21, and N22; round 21 adds N23 and corrects N20's
`--in` to extend. Round 22 settles N23 and lands the `count(...)` wrapper
in `ember/ember`; N20, N21, and N22 are still proposals the owner has not
confirmed, and nothing in §4.14 is code yet. Round 23 adds N24 and
settles it: `--out` is withdrawn and a run's answer is the delivery
channel; Q35 survives for typed fields and dies for files, N3 dies with
the file cells, and N14 is void. Round 27 settles N27 and N28 together:
one global hearth and one database for all spaces, both in code.
Round 28 lands the N25 (b) human gate and adds N29 about the daemon's
name.

Dead with the bus: Q8, Q10, Q12, Q13, Q14, Q16, Q20, Q22, Q23, Q24,
Q28, Q32, Q34, Q40, Q41, Q42, Q44.

## 9. Sources and assumptions

Sourced: the owner's round-9 message; `ticket.md` `## Verified`;
`wisp/wisp` `new_session` 209–240 (no `-d`), `steer_command` 857–878;
the round-9 probes in §6.2, run on this host.

Round 10 added, measured on this host with strace 6.8: the curated
syscall set costs 0.32 s and 0.66 MB on one `python3 -c pass`, against
0.51 s and 2.3 MB for `%file`; a fixed 9 ms per traced process; a
traced `bash -c 'touch x; python3 tool.py'` reports the read of
`~/.config/research/cfg.toml`, the append to a source file outside the
work dir, the create of `out.md`, and the delete of `gone.txt`, over 18
pids; `unlink("gone.txt")` carries no resolved path, so a per-pid cwd
tracker is needed and `chdir`/`getcwd` are traced for it.

Assumed, each with its check: `ember result set` rides an existing tool
round (one fake-endpoint run); the run lock survives a hearth crash
(ten timed starts, no model); a rule evaluation over a 1k-atom log is
sub-millisecond (a unit test on a temp store); the rendered
`<environment>` is byte-identical across a session's runs, so the prefix
cache holds (two requests compared on a fake endpoint).
