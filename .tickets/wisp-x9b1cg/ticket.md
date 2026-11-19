---
id: 'wisp-x9b1cg'
name: 'ember coordinator: rule engine, global daemon, and human gates'
status: 'wip'
created: '2026-11-13T08:33:56Z'
parent: null
blocked-on: []
---

## Goal

A coordination mechanism with a control plane for `wisp`: namespaces of
wisps that exchange addressed messages, wake each other, share a
concurrency cap, spawn helpers, survive crashes of both a wisp and the
control plane, and expose everything to a UI.

Full design: `design-options.md` (round 4, S0–S11, with round-5 and the
transport amendment of this session). API contract: `api-spec.md`
(round 3, amended this session for the W0 withdrawal; round 2 was
falsified by child `falsifier-api`, seven findings, all repaired). The
wisp plan is `wisp-changes.md`; the point-by-point review answers are
`review-answers.md`. §13 holds two worked examples: a minimal two-wisp
run and a full-surface run, both from daemon start to stop, with a
coverage table for every verb and exit code. Round 12 implements v0 and
the nine wisp changes; the design and the API contract above remain the
earlier records.

**Round 7 pivot (this session, owner).** The goal changes: not peer
self-coordination, but declared agent types and rules, task
submission, and a rule engine that runs agents until the work
settles. Decomposition replaces delegation: an agent splits work
into N runs plus a continuation, and agents add rules through the
same API the owner uses. Cross-space coordination is deferred.
First-principles exploration with three designs (Loom, Foreman,
Ledger) and an axis decomposition: `rule-engine-options.md`. The
old gap rows below are re-mapped there §7. The pick is open (Q25);
no code before it settles.

**Round 8 (this session, owner).** Three amendments and one surface.
Cross-agent steering is out; the only steer is the user's, and a user
steer of a space starts a new agent that inspects live runs and rules
and reshapes the space. "Hard wake" is not a name to keep: a run returns
or decomposes, and every start is a start. Delivery ack is dropped. The
Ledger is the closest design ("the language is arcane"), and the owner's
`ember rule add` examples replace the Loom template file with rule rows.
The review, the first principles, thirteen language axes, eight
findings, and a proposed definition are `rule-language.md`. The
system-level axes collapse; the open space is the language (Q35-Q44).
No code.

**Round 9 (this session, owner).** The owner answered the thirteen
language axes and the eight findings. Four answers overturned a
round-8 proposal: the outcome domain moves from the agent type to the
rule (`--require passed:bool`, and the field name becomes the event
verb); `--cap` becomes an atom count expression; the engine never
steers a live run, so `ember steer` writes an atom and starts a steward
run; the root rule layer is dropped for v0. Two answers replace a
round-8 object outright: an agent type is now a wisp session directory
made with `wisp new -d`, forked per run, with no type file format; and
file-change capture moves to a per-run working directory plus a stdlib
snapshot, after a scout that found namespaces unavailable on this host.
The amended language is `rule-language.md`; W1 is no longer needed by
ember, and W7 and W11 become load-bearing. No code.

**Round 10 (this session, owner).** The owner answered six follow-ups and
one documentation request. The steward run may `wisp steer` live runs; a
second `ember steer` while a steward is live joins it, because a steer joins
a live run of its target by law and needs no flag, so the steer lock (W1)
returns to the required set. Every failure reason gets a named report:
field, type, run, rule, version, trigger atom, times, re-prompt, and fix
command. `agent-type:T.done` becomes the closure of a decomposed job: every
run carries an inferred parent (the lowest common ancestor of the trigger
runs), the atom fires once per root when the whole tree is green, a repair
stops a failure poisoning its tree, and `agent-type:T.failed` stays a
per-run fault. `wisp fork` stops rewriting records: the `<environment>`
block renders at request time from `wisp.run.json` and `-d` (W13), so a fork
is a plain copy. Every `ember` verb takes a body only through `-F FILE` or
`-F -`. File capture is syscall-based: `strace -ff -y` with a curated set
wraps every engine-started run, so a worker editing source or a research
agent reading `~/.config` is visible; the per-run work dir stays for
declared outputs, not for attribution. The required wisp set is nine items.
No code.

**Round 11 (this session, owner).** The owner asked whether the
environment switch belongs on `wisp build-system-prompt` instead of
`wisp new`: a `build-system-prompt` flag emits the system record, the
record carries an `include_env` marker, and `wisp run` renders the block.
The recommendation is yes, with the record-encoding flag named `--record`
(alias `--wisp-jsonl`) and the switch named `--include-env`. The marker
then rides the record, `new -s` stores bytes and composes no text, the
`-s`-without-env error path disappears, and a fork carries the marker
unchanged. `wisp.run.json` keeps `created` and `project_dir` and drops
`env_in_system_prompt`; `sessions_root` derives from `-d`'s parent. The
question is N9. No code.

**Round 12 (this session, owner).** The owner asked for the whole
implementation, with a falsifier subagent and `ocr` review loops. Code
landed in `ember/` (one stdlib program, `ember/ember`, plus
`ember/README.md` and `ember/tests/`) and in `wisp/wisp`: W1 (steer
lock), W2 (run lock, exit 76), W4 (exit table and machine line), W5
(`status --json`), W7 (`fork`, plain copy, shared source lock), W10
(`--no-stream`), W11 (`new -d DIR`), W12 (`--wallclock`, default 600 s,
0 disables), and W13 (request-time `<environment>`, the marker on the
system record, legacy blocks stripped and re-rendered). N9 is settled
as (a): `build-system-prompt --record` emits the system record and
`--include-env` sets its marker; `new -s` stores bytes and composes no
text; `new --env-in-system-prompt` remains as a compatibility alias
that only sets the same marker. Tests: `tests/test_wisp_changes.sh`
(26 checks), `ember/tests/test_flow.py` (19 checks), the existing
shell and unit suites, and three `ocr` passes plus two falsifier
passes; remaining findings are low or accepted by the design.

**Round 13 (this session, owner).** The owner asked what happens when a
run's time or context runs out, and set the wanted default: distill and
continue. The code facts: `ember` starts every run as `wisp run
--no-stream --wallclock $EMBER_WALLCLOCK` (default 600 s) and never
passes `--context-guard`, so a run has no context limit; exit 124
becomes `finish_failed(reason=wallclock)` and exit 75, if ever armed,
becomes `finish_failed(reason=guard)`, both before the contract check,
so neither distills and neither calls `wisp continue`, though the run
dir stays resumable by hand. A context exhaustion without a guard
surfaces as an endpoint error (exit 77) and falls into the contract
check with one re-prompt. The wanted default is the `wispy` shape
already settled in Q19: a distill turn with no guard in the same
session, then a fresh session seeded with the handoff. The owner also
asked for a generic worker, an `ocr` reviewer with a go/no-go, and a
three-loop cap; the rule shape is worked out and written in
`ember/README.md` ("Recipe: a worker and an `ocr` reviewer"), with the
exhaustion path carried by a `distiller` type plus a `--run .parent`
`resume` rule. Four language facts constrain that recipe: a required
field named `done` writes `agent-type:T.done`, which `infer_parent`
treats as closure and a new root; `--cap EXPR<N` counts atoms
space-wide before each firing, so a cap on the atom the finished run
just wrote grants N-1 restarts; `run_answered_fault` accepts an
`agent-type:T.failed` atom whose `fields.run` is the failed run, so a
distiller rule answers the fault; and `tree_ok` on a failed run takes
`any` answering child, so a resume placed as a sibling of the distiller
is invisible and must hang under it instead. The recipe is not executed
yet. No code.

**Round 14 (this session, continuation after a wallclock-killed run).**
The recipe test is blocked: `ember/tests/test_flow.py` fails three of
its nineteen checks, all steer checks (one run wanted, two created;
zero joins; zero delivered steers), reproduced four of four. The cause
is a startup race in the join, verified with no paid call: `admit`
marks a run row `live` right after the spawn, the spawned `wisp run`
holds `wisp.run.lock` about 0.36 s later, and `run_is_live` on a
`live` row demands the held lock, so a steer firing inside the window
finds no live target and starts a duplicate. `wisp steer` itself is
not at fault: a manual append to a live run returns 0. The fix follows
W2's law that the lock is the liveness record: a spawned run stays
`starting`, a state `run_is_live` already counts as live, until the
lock is held, and `Hearth.poll` promotes the row to `live`; `admit`,
`run_is_live`, `reconcile`, and `command_why` are the only readers of
state `live`, and `LIVE_STATES` already includes `starting`, so the
cap and settling do not move. No code changed this round; the
wallclock pair-space experiment and N10-N13 stay open.

**Round 15 (this session, owner).** The steer-join startup race is
closed and the round-13 recipe runs. Two code changes: `admit` no longer
marks a spawned run `live`; the row stays `starting` (a state `run_is_live`
already counts as live) until `Hearth.poll` sees `wisp.run.lock` held, so a
steer firing in the 0.36 s spawn window joins the run instead of starting a
duplicate. Then the recipe test found a second defect: `ATOM_RE`'s verb
group `[^.]+` swallowed the comparison, so `agent-type:distiller.handoff=true`
stored verb `handoff=true` and op `null`, and every comparison event in
`--event` never fired — the README's `approved=false` and `handoff=true`
rows among them. The verb class is now `[^.=<>!]+`. The recipe flow
(`flow_exhaust` in `ember/tests/test_flow.py`) runs the README's `rescue` and
`resume` rows against a hanging endpoint with `EMBER_WALLCLOCK=4`: the
worker fails `wallclock`, the distiller writes `handoff.md` and sets
`handoff`, `resume` starts a worker under the distiller (`--run .parent`),
and the space settles green with `agent-type:worker.done`. Tests: 34 checks,
three consecutive full runs. N10-N13 stay open.

**Round 16 (this session, review of round 13's request).** The question
"what happens when the time or context runs out" is answered in
`ember/README.md` ("Time and context today"): `ember` passes `--wallclock
$EMBER_WALLCLOCK` (default 600 s) and no `--context-guard`, so a wallclock
stop is exit 124, a guard stop would be 75, and both become
`finish_failed` before the contract check, while a context exhaustion
without a guard arrives as an endpoint error (exit 77) and takes the
one-re-prompt contract path. The **default** the owner asked for is still
not an engine default: the distill-and-continue behavior is today a space
pattern (`distiller` type plus `rescue` and `resume` rows), which is N10
option (b). N10-N13 stay open, so no engine default was written. The
recipe's other half — the `ocr` reviewer loop — is now executed: a new
`flow_loop` drives `pickup`, `review`, and `loop` against a critic that
always answers `approved=false`, with `--cap agent-type:hand.ready<4`. The
space holds four worker runs and four critic runs, all done, four ready
atoms, four no-go atoms, then `rule:loop.capped`; the closure
`agent-type:hand.done` fires and `space.settled` carries an empty `red`.
That last fact corrects the README, which claimed the fourth no-go settles
the root in `red`: `.done` is the closure of a finished tree, not an
approval, so a rejected job closes green and the verdict must be read from
the `agent-type:reviewer.approved` atoms or the `review` cell. A harness
race surfaced on the way: `wait_settled` read only run states, so it could
return in the gap between a finished run and the firing of that run's atom,
and `flow_success` once saw one run of two; the wait now also requires
`space.settled` to be the newest atom. Tests: 46 checks, no paid call.

**Round 17 (this session, design review of the recipe's cell names and a resource proposal).** The owner asked two things. First, `answer:answer.md` and `review:review.md` in the round-16 recipe: the design defines only `task:`, `session-file:`, `steer:`, and `result:` as cell categories (`rule-language.md` §4.2), so `answer:` and `review:` are not design concepts. They work because `cell_ok` accepts any `CATEGORY:VALUE` and `--out` injects only the value after the colon as `work/<rid>/<VALUE>`; the category is part of the cell name and is dropped from the filesystem path. The cells are distinct only because their full names differ; `session-file:answer.md` and `session-file:review.md` would be equally distinct. The correction is to use `session-file:` in the recipe and to decide whether `rule add` should reject any other category. Second, the owner proposed a space-owned `resource/` folder with a copy-in verb, and a rule target `--resume resource:distill.md` that distills a failed run in its own session, the `wispy` shape. The recommendation is yes to the resource, with three constraints: a resource is an immutable space file with a recorded hash, referenced only by a space-relative name and added through `-F`; `--distill RESOURCE` is a one-run target that forks the trigger run's session dir, runs the resource text appended to the briefing, and declares its own outputs and required fields; the fresh continuation is a second `--run .parent` row, not a second run inside the same rule. The resource can replace the distiller agent type for the same-session shape: no distiller persona and no distiller session, and the distill turn sees the work conversation. The separate distiller type remains a valid `--run` target, so the recipe can offer both shapes. Two facts bound the shape: the distill run's type must differ from the failed type, or its own failure retriggers the rescue rule; and `spawn_run` passes no `--context-guard`, so a context exhaustion is an endpoint error after the hard limit, and the distill prompt may not fit. The wallclock case works without a guard; the context case needs the guard that N11 asks for. N10 settles as (b): the owner prefers a rule to an engine default, so the engine distills nothing by itself and a guard stop writes only the fault atom. The `/` root marker in the owner's `resource add` example is dropped: a relative destination name already roots at `<space>/resource/`, and a leading `/` reads as an absolute path. N11-N17 stay open. No code.

**Round 18 (this session, owner).** The owner rejected `--distill`: the
point is to continue a stopped run as `wispy` does, and round 17's
one-run target conflated the continuation with the copy. The owner's
framing: `--run` starts a new agent; a second target resumes the agent
with a prompt; a third forks it; and `--context-guard` and `--wallclock`
belong on the rule. Still design only. The mechanism facts settle the
mapping. `wisp continue` reads no stdin, appends no prompt, and only
finishes an open segment, so the prompt-bearing continuation is `wisp
run -d <the same dir>`, which appends the user record and drains a stale
inbox; wispy's distill turn is exactly `wisp run -d <session>` with no
guard (`wispy/wispy` 495-503, 858-899). `wisp fork -d SRC -o DST` copies
`wisp.jsonl`, `wisp.run.json`, `wisp.modelcfg`, and an empty
`wisp.usage`, sets a fresh `created`, takes `-m`/`-t`, and refuses a busy
source (`wisp/wisp` 1218-1285). No wisp change is added: the nine stand,
and the new targets reuse W7, W10, W12, and the existing
`--context-guard`.

The surface is three targets, one per rule: `ember rule add --event E
(--run TYPE | --run .parent | --resume | --fork) [-F BODY] ...`.
`--run` is a fresh agent from `agent-types/TYPE`; `--resume` is one more
turn in the trigger run's own session dir, with BODY as the prompt;
`--fork` is one more turn in a copy of that session. Both inherit the
trigger run's type, so the persona is the source's; a different persona
needs `--run TYPE` and file inputs, because a fork copies the system
record and no record is rewritten (W13). BODY enters through `-F` (R10f)
and is stored on the rule row; `--resume` and `--fork` require it and
`--run` refuses it. Both require a conjunct that names a run, and `rule
add` refuses a `started` conjunct, so a source is terminal by
construction; a firing whose source is not terminal fails `busy`.
`--resume` keeps the source's work dir, because the stopped run's files
are the job's files; `--fork` copies the work dir, so the branch writes
its own. The shared session dir puts two runs' rows in one
`results.jsonl`, so a result row now names its run and the engine reads
only its run's rows; otherwise a stale field from the source would
satisfy the new contract.

Policy: `--guard LIMIT` and `--wallclock S` on the rule, stored on the
rule and the run row so a re-prompt inherits both. `--guard` passes to
wisp unchanged, so `70%` resolves against `wisp.modelcfg` (wisp
refreshes it from `WISP_LLM_MODEL_INFO_FILE`) and `150k` needs nothing;
`rule add` checks only the form. The guard must leave room for the
continuation: a guard-stopped session sits at the limit, and a guarded
resume stops at its first round, so the worker rule guards at 70% and
the resume rule carries no `--guard`. `EMBER_CONTEXT_GUARD` is dropped
(N11 settles as the rule flag), N12 settles as a new run row over the
same dir, N16 settles as the three targets, N15 settles with no resource
store (the prompt is the rule's body), and N17 settles as `--guard`.

Consequences: a resume or fork run's parent is the trigger run, so it
answers that run's fault atom and a green continuation turns the failed
run's tree green; a resume of a done run is a child of that run, so a
failed resume turns that tree red. A failed resume writes
`agent-type:T.failed` again with its own run id and retriggers its own
rule, so a rescue rule needs a cap. The `.` target prefix reserves
`.parent`, `.resume`, and `.fork`; `create_run` picks the source dir and
work dir, `prepare_run_dir` forks the source for `--fork`, `spawn_run`
adds `--context-guard`, `failure_report` names the continued run, and
the README keeps the round-17 recipe until the flags exist in code. Two
proposals ride along: the fault atom's value becomes the reason, so
`--event agent-type:T.failed=guard` selects (N19), and a fork rule may
take `--model` to carry Q17's fallback pair (N18). No code.

**Round 19 (this session, owner).** The owner answered the four open
N-questions and asked for the updated recipe. N13: a wallclock stop is a
failure, period, so the engine checks no contract after exit 124 and the
space-level rescue is the only continuation. N14: `session-file:` and
`resource:` are the two `--out` categories, and a `resource:` output
lands in `<space>/resource/` instead of the run's work dir. N18: a rule
may carry `--model` and `--thinking`, passed to `wisp fork`. N19: the
fault atom's value is the reason, so a rule selects one reason.

Code landed in `ember/ember`: the three targets (`.parent`, `.resume`,
`.fork`), per-run result rows, `--guard`, `--wallclock`, `--model`,
`--thinking`, the `--out` category check, `resource:` output paths, the
fault atom's reason value, `mode`/`source` columns with an `ALTER TABLE`
migration for older stores, `prepare_run_dir` returning `(error, reason)`
so a live source fails `busy`, and `EmberExit` so a refused argument's
text survives the hearth's error reply (before, a bad `--event` or
`--out` answered `error: 2`). `--model` and `--thinking` cover every
target that forks a dir, including `--fork`; `--resume` keeps the model
pair and refuses both flags. `ember/tests/test_flow.py` grew
`flow_guard`, `flow_resume`, and `flow_fork`, and the scripted endpoint
now reports usage on every final chunk, so a `--guard` rule stops at a
round boundary: 102 checks, no paid call. The README recipe is rewritten
on the three targets: two agent types, five rules (`pickup`, `review`,
`loop`, `rescue`, `continue`), `session-file:` cells plus one
`resource:review-latest.md`, a `--guard 70%` worker, an unguarded
`--resume` rescue capped at three handoffs, and a `--run .parent`
continuation capped at four worker runs.

**Round 20 (this session, owner).** The owner asked for the recipe split
in two — a review loop (worker picks up, reviewer runs on success or
failure, loop at most three times) and a distill loop (worker hits a
wallclock or guard cap, resume produces a handoff, a new worker
finishes, at most three times, the job succeeding when any worker
succeeds) — and proposed splitting rules into agents and rules:
`ember agent add NAME --type T --require --in --out --guard
--wallclock`, with `ember rule add --event E --run agent:NAME` holding
only event, target, and cap. The recommendation is yes (N20): an agent
row is a named run contract, a rule-level `--in` replaces the agent's
inputs, `--resume agent:X`/`--fork agent:X` take their body from the
agent row (which returns the round-17 resource wish in a better form
than the N15 (d) rule body), `.parent` leaves the recipes, and bare
`--run TYPE` stays as the anonymous form. N1 is subsumed: the agent row
is the shared contract. Two facts found by source read: the round-19
rescue cap `handoff<3` never blocks a failing distill, because only a
successful resume writes a handoff atom, so the distill loop's budget
counts `agent-type:worker.failed<4` instead; and `.out` takes the
latest cell version, so a reviewer on a failed worker may read a stale
answer from an earlier loop round — the persona must branch on the
trigger line and read `ember query run:<id>`, which prints the stored
failure report. "Success or failure" needs an event disjunction (N21,
` or ` between alternatives); today two rules over one agent do the
same. The two recipes are written out in `rule-language.md` §4.14; the
README keeps the implemented surface with a design note and the
corrected rescue cap. No code.

**Round 21 (this session, owner).** Two questions about the proposed
recipes and one defect found while answering them. First,
`--cap 'agent-type:reviewer.approved<4'`: the `<4` is the count
threshold, not a comparison on the `approved` field, which is a bool;
`parse_cap` splits the trailing `<N` and `count_cap` counts matching
atoms space-wide, so `approved` is the atom whose occurrences are
counted and its value is ignored. The owner's `ran` counter is rejected:
a counter atom is a derived fact with a writer, it drifts when a counter
write is lost, and it counts starts rather than finished runs; the count
over terminal atoms is arithmetic and cannot drift. The recommended
spelling is `count(EXPR)<N`, which also reads correctly with a value
test inside the count (`count(agent-type:worker.failed=guard)<3`); N23.
Second, a probe showed the ambiguity is not only cosmetic:
`agent-type:reviewer.approved<4` in `--event` matches both
`approved=true` and `approved=false`, because `conjunct_matches` coerces
a bool atom to int (`int(True)=1<4`, `int(False)=0<4`), while
`agent-type:worker.failed<4` never matches the string reason. The fix is
type-strict matching plus an `add_rule` refusal where the field's
declared type is known. Third, the `continue` rule's repeated
`--in task:prompt`: §4.14 said a rule-level `--in` **replaces** the
agent's inputs, which would have dropped the task from the continuation,
so the owner's reading is the right semantics. §4.14 now says the rule's
`--in` **extends** the agent's list (agent entries first, exact repeats
dropped, merged list on the run row), and the recipes drop the repeats.
A related source fact: a `cells` row records the writing run, but
`briefing_of` resolves `.out` through `latest_cell`, so the design's
"`.out` is the triggering run's output version" is unimplemented; the
split fixes the resolution and a failed trigger prints `(no output
version yet)` instead of a stale path. No code; N20-N23 stay open.

**Round 22 (this session, owner).** The owner agreed on the `count()`
wrapper and drew the line it draws: the arithmetic is the count of
atoms, while a predicate on a declared field is a test of one atom's
value. So `--cap 'count(agent-type:reviewer.approved=false)<4'` counts
only the no-go atoms, and `--event agent-type:reviewer.defects>5` over a
`--require defects:int` tests the int a reviewer reported. N23 settles as
(a) and lands in `ember/ember`:
`parse_cap` takes `count(EXPR)<N` only and fails the bare form with exit
2 and a message naming `count(`; `cap_text` renders the stored cap, so
`rule show` and the run briefing print `count(EXPR)<N`; a stored
`{"expr","n"}` row from round 19 reads unchanged, so no store migration.
Two defects fell out of the same pass. First, `count_cap` took the
counted atom's subject literally, so `me` counted nowhere and `id:X`
counted nothing; the count now resolves subjects through
`target_subjects` with the rule, as a firing does. Second,
`conjunct_matches` coerced across kinds, so `int(True)=1` let
`agent-type:reviewer.approved<4` match both values; matching is now
type-strict, `(row value_type or literal kind) != literal kind` returns
`False` except for `!=`, and `rule add` refuses a comparison the
declared field type cannot carry (a kind mismatch, an ordering op on a
bool, or one field declared with two types in the space). A third,
smaller fix: a hearth-side refusal answered exit 1 for every `rule add`
argument error, because the exit code was dropped at the socket. The
answer now carries `code`, `refusal_code` reads `EmberExit`'s code or
`2` for a `ValueError`, and the client exits with it, so a refused
`--cap`, `--event`, or `--out` exits 2 as a locally refused argument
does. Tests: `ember/tests/test_flow.py` runs 125 checks, a new
`checks_cap` unit section covers the grammar, the type-strict match, and
the `rule add` refusal without a hearth, `flow_loop` adds the refused
bare cap inside a live space and the value-split count of the four no-go
atoms. `ember/README.md` and
`rule-language.md` §3.1, §4.4, and §8 carry the wrapper. N20, N21, and
N22 stay open.

**Round 23 (this session, owner).** The owner read `ember/README.md` and
found two faults: the file never shows an agent definition, and `--out`
looks useless, because every example names one session file while a run
already delivers through its final assistant message. Both are answered.
The README now opens an **Agents** section: the persona file, `wisp
build-system-prompt --wisp --record --include-env` as the system record,
`wisp new -d <space>/agent-types --name T -s T.sys.json` as the type, and
what a run adds (its dir, work dir, briefing, guard, wall clock, rule).
A new **The answer** section states the delivery: the engine reads the
triggering run's last assistant text from `<run dir>/wisp.jsonl` and
writes it into the next briefing as `answer: run <rid> (<type>)`, so no
rule declares an output. `--out` is withdrawn; N24 settles as (a).

Code landed in `ember/ember`. Gone: `--out` and its store categories,
`OUT_CATEGORIES`, `parse_cells`, `out_cell_ok`, `output_path`, the
`no_output` and `no_change` contract, the output half of `finish_success`
and `briefing_of`, and the space `resource/` directory. New: `answer_of`
(the last non-empty assistant text in a run dir), `clip_answer` (16 KiB,
head 12 KiB plus tail 4 KiB around one line naming `ember query
run:<id> --json`), and `answer_block` (the briefing's `answer:` section,
or `answer: none (run <rid> (<type>) ended with no final message)`).
`contract_problems` now reports `no_response` and `no_result`;
`reprompt_text` and `failure_report` carry a fix line for each;
`ember query run:<id>` prints the answer and `--json` carries it as
`answer`; `row_json` drops the dead `outputs` key while the column stays
at `[]`, so an older store reads unchanged. `add_rule` refuses a `.`
reference in `--in` with a message naming the default. `run_of_atom` now
accepts the briefing's decoded atom dictionaries, which the new
`answer_block` passes.

Two facts bound the design. A run cut by a wallclock or a guard keeps its
last text, so the answer survives a stopped run; a run whose *last*
record is a bare tool call has no text and prints the `answer: none`
line. And a textless turn never reaches the engine: `wisp` fails it with
exit 79 (`degenerate`) after its retries, so `no_response` fires on the
crash-and-adopt path: `reconcile` adopts a run whose lock is free, finds
its fields set, and would otherwise mark it done with no answer.

Tests: `ember/tests/test_flow.py` runs 141 checks, three consecutive full
runs, no paid call. The fake endpoint now plans one run from the
briefing's header and answers with text naming what it left
(`designed it`, `reviewed, no go`), so the flows follow the answer
instead of a cell; a new `checks_answer` section covers the reader, the
clip, and both contract reasons without a hearth. Q35's file half is
withdrawn and its typed half survives; N3 dies with the file cells; N14
is void. `rule-language.md` carries the change as §0.6, with §3.3, §4.2,
and §4.5 amended and N24 in §8. No commit.

**Round 24 (this session, owner).** Two asks. First, the hearth
restated: there is no single global daemon — one hearth tends one
space (`ember hearth start`, `<space>/hearth.sock`), and the `ember`
CLI is a stateless client whose mutating verbs go through the socket,
because the chain run→atom→rule→run needs a process alive when a run
exits: `Hearth.pump` fires rules on landed atoms, `admit` fills cap-3
slots at moments no CLI process witnesses, `Hearth.poll` reads child
exit codes and promotes `starting` to `live` on the held lock, the
steer join needs the watcher inside the 0.36 s spawn window, and the
one-writer law serializes the store. `ember/README.md` gains a "Why a
hearth" section. Second, the human gate: three designs written as
`rule-language.md` §4.15 — (A) the owner's `--require-human` gate row
(a `gates` table, `ember gate answer`, atoms `gate:<rule>.FIELD`, and
gate branches in settle, closure, and trees, because `tree_settled`
and `tree_ok` read runs only); (B) the human as a manual agent type
(`--run human:LABEL`, run row `mode manual` in state `waiting` —
`NONTERMINAL` without `LIVE_STATES`, so it blocks settlement and
closure, holds no slot, and needs guards on `admit`, `reconcile`, and
`answer_of`; `ember answer` completes it through the unmodified
`finish_success`, so atoms are `agent-type:LABEL.FIELD` and the loop
rule is the existing reviewer loop); (C) an atom-only `--gate NAME`
with no waiting state, which cannot pair a question with its job and
settles with the question open. The recommendation is B; the state
lists already split the waiting semantics, the run row already
carries the tree semantics, and the only additions are one target
spelling, one state, one verb, and four guards. N25 asks the pick,
N26 the dismissal; dynamic asking stays deferred by the owner. No
code.

**Round 25 (this session, owner).** The owner asked whether one global
ember daemon can replace the per-space hearth, whether the shared
concurrency cap was dropped by accident, and picked design B for the
human gate. The cap: dropped by accident. The Goal still says "share a
concurrency cap" and Q2 says a constant 3, but round 12's gate was "v0
is one space end to end", so the hearth came up per-space
(`admit` counts `live_runs` on one space's `ember.db`, the socket is
`<space>/hearth.sock`, and no cross-space state exists), two hearths
give six concurrent runs, and round 24's README line "there is no
single global daemon" restated that implemented shape with no decision
behind it. The feasibility: yes. Every hearth duty — `Hearth.pump`,
`admit`, `Hearth.poll`, the steer-join window, the one-writer law,
`reconcile` — is per-store, not per-space, so one daemon can hold N
per-space stores: a space stays a self-contained directory with its own
`ember.db`, the CLI keeps `--space`/`EMBER_SPACE` as a field in the
request payload, the global cap is one live-run count across the
daemon's open connections with round-robin admission so one hungry
space cannot starve another, and `reconcile` iterates the registry at
daemon start. The blast radius is named: a daemon restart pauses pump
and poll for every space, but a spawned run carries no `PDEATHSIG`, so
runs survive orphaned and `reconcile` re-adopts them; a per-space stop
needs a pause flag; `serve`'s `chmod(space, 0o700)` loses meaning and
authority moves wholly to the socket (S10 unchanged, 0700 plus
SO_PEERCRED later). The round-7 deferral holds: rules, atoms, cells,
trees, and steers never cross spaces, and only admission is global —
which is the Goal's shared cap, not the deferred bus. The alternative
— per-space hearths plus a crash-safe `flock` slot ledger held for a
run's life — works without a global daemon but adds a second mechanism
and splits the live-count truth. The question is N27, recommended (a),
and the owner wants it settled before any code; the README's "Why a
hearth" first line changes when it settles. N25 settles as (b), the
manual agent type; N26 stays open, reframed under B as failing the
waiting run. No code.

**Round 26 (this session, owner).** The owner asked what a single DB
costs if the hearth goes global: one SQLite file for all spaces makes
listing spaces and collecting metrics one query, which a UI wants.
Three losses are named. First, the space stops being self-contained:
today a space is one directory (`ember.db`, `runs/`, `work/`,
`agent-types/`, `cells/`, `logs`, `hearth.sock`, `hearth.pid`), so copy,
archive, delete, and inspect are file operations and the directory's
existence is the registry; with one file the registry becomes a
`spaces` table holding each space's path, `rm -rf` leaves orphan rows,
a moved directory breaks the path-to-rows pairing, and portability
needs an export verb. Second, the round-7 isolation — rules, atoms,
cells, trees, and steers never cross spaces — is today physics: no
query can see another space because no other space is in the file. One
DB moves that invariant to discipline: every table (`atoms`, `rules`,
`runs`, `consumed`, `joins`, `cells`, `files`) and every fixed `meta`
key (`settled`, `report:<rid>`, `closure:<root>`) gains a space
binding, and a missing filter is a cross-space leak the design
forbids; `atoms.seq` also globalizes, so per-space ordering survives
but "newest atom" checks must filter by space; cell names are
user-chosen, so they collide across spaces without the binding. Third,
one corrupted file takes every space's history, where per-space files
isolate. What one DB buys: listing spaces and cross-space metrics are
one query with joins; the global cap becomes exact by construction
(`live_runs` over one file — no cross-store count, no round-robin to
keep honest); the one-writer law simplifies, because the
single-threaded hearth is the only writer of one file; one global seq
orders events across spaces, which per-space files cannot do without
timestamps; and the CLI's read verbs open one fixed path instead of
`<space>/ember.db`. Two bounds on the win. The observability gain is
partial: answers, work dirs, traces, and session logs stay per space
on disk, so a UI reads the control plane — states, times, reasons,
atoms, reports — from the one file and walks the filesystem for
content. And the single DB requires N27 (a): N27 (b)'s per-space
hearths are several writer processes and cannot share one file, so
choosing the store decides the daemon's shape. The recommendation is
one DB with the losses bought deliberately: a `spaces` registry table
(id, path, paused), a space binding threaded through one query choke
point so the filter is not per-call discipline, an `ember space
export` verb for portability, and content left on disk. The rejected
middle: per-space files plus an `ATTACH`-based UI works for a handful
of spaces but gives no global seq and no one-file listing, and a
daemon-written rollup metrics DB is a derived copy that drifts, the
same fault that killed N23 (d). The question is N28, coupled to N27.
No code.

**Round 27 (this session, owner).** The owner settled both scope
questions and asked for the implementation: one global hearth (N27 a)
and one database for all spaces (N28 a). Code landed in `ember/ember`.
`state_root()` (`EMBER_STATE_ROOT`, default `~/.local/state/ember`,
0700) holds `ember.db`, `hearth.sock`, `hearth.pid`, and `hearth.log`;
`ember hearth start` takes no space, `serve` binds one socket, and the
request payload carries the space, resolved by the CLI from
`--space`/`EMBER_SPACE` and by the hearth to a registry row
(`ensure_space`: a `spaces(id, path, paused, created)` table; the
directory path is the binding, so a moved directory is a new binding and
export is the escape hatch). Every table (`atoms`, `rules`, `runs`,
`consumed`, `joins`, `cells`, `files`, `meta`) and every fixed meta key
gains the space binding; `atoms.seq` globalizes, run ids stay unique in
one file, rule ids and cell names become per-space (`PRIMARY KEY
(space, id)`, `(space, name, version)`), and every query filters by the
binding — the round-7 cross-space isolation stays physics. The cap is
one count: `admit` counts `live_runs_all` across every space and
`next_pending` picks pending rows round-robin (a cursor on the hearth),
skipping paused spaces, so a slot freed in one space starts a pending
run in another. `reconcile_all` walks the registry at daemon start and
`Hearth.poll` derives each run's space from its row. New verbs:
`ember space list`, `ember space pause`/`unpause`, and `ember space
export [-o FILE]`; `space init` registers through the hearth, `open_read`
checks the registry, and a request with no hearth answers a clean
`the hearth is not running` instead of a traceback. Per-space stores
from rounds 12-26 are not migrated. Tests: `ember/tests/test_flow.py`
runs 166 checks — a new `checks_global` (round-robin alternation, the
paused-space skip, the cross-space live count, per-space meta) and a new
`flow_global` (two spaces on one hearth sharing a rule id and a type
name, cross-space invisibility, the global cap holding four hanging jobs
to three slots across two spaces, pause holding a pending run, export
carrying one space's rows) — three consecutive full runs, no paid call.
`ember/README.md` and `rule-language.md` §0.7, §4.10, and §8 carry the
change. No commit.

**Round 28 (this session, owner).** Two asks. First, the hearth's
name: a space is data and the hearth is the only process, so `ember
space start` names the wrong thing — one daemon serves every space,
`space init` registers the data, and `space pause`/`unpause` gates one
space's admission. The name itself is a round-2 metaphor that still
fits (one hearth tending every ember), and `ember daemon start` is the
honest rename if the metaphor must go; the question is N29,
recommended (a) keep. Second, the N25 design-B human gate landed in
`ember/ember`. `--run human:LABEL` (a reserved `human:` prefix; LABEL
is a pseudo-type with no `agent-types/` dir) opens a run row with
`mode manual` in the new state `waiting`: `NONTERMINAL` gains
`waiting` and `LIVE_STATES` does not, so a gate blocks settlement and
closure exactly as a live run does, holds no cap slot, and `admit`
never picks it. The rule's `-F` body is the question on the row's
briefing, read through `ember query run:RID` (a `question:` block) or
`ember trigger show`; `ember answer RID --field F=V... -F FILE`
type-checks the declared fields through the shared `typed_value`
(so `ember result set` fails the same way on a bad value), stores the
answer text on a new `answer` column, and calls the unmodified
`finish_success`, so the atoms are `agent-type:LABEL.FIELD` and
`run:RID.done` and the loop rule is the reviewer loop with a human in
the chair. `answer_of_row` reads the stored text for manual rows, so
the next briefing's answer block works; `reconcile_space` skips the
state `waiting` and `mode manual`, so a hearth restart leaves a
dirless gate waiting; `rule add` refuses `--guard`, `--wallclock`,
`--model`, and `--thinking` on a `human:` target and stores `trace
none`; `ember result set` refuses a manual run; `command_why` lists
`waiting:`; a manual run's briefing closes with `ember answer`
instructions instead of `ember result set`. `ember/README.md` gains a
"Human gates" section; `rule-language.md` §4.15 B carries the landed
surface (the string type is `str`, and `ember gate list` was never
built). Tests: `ember/tests/test_flow.py` runs 202 checks — a new
`checks_gate` (the waiting arithmetic, the reconcile skip, the manual
answer reader) and a new `flow_gate` (the gate opens after the worker,
holds no slot, blocks settlement, survives a hearth restart, refuses a
bad bool, a missing field, `result set`, and a re-answer; one
rejection restarts the worker under the gate with the human's answer
in its briefing; one approval settles the space green) — three
consecutive full runs, no paid call. N26 (the dismissal verb) and N29
stay open.

**Round 29 (this session, owner).** The owner answered N29 with the
rename and one question about the files: `ember daemon start`, and
`ember.sock`, `ember.pid`, `ember.log` in the state root. Both are code
in `ember/ember`. The verb is `daemon start|stop|status`, the hidden
`_serve` action spawns `daemon _serve`, and `ember hearth` is gone with
an argparse exit 2. `Hearth` is `Daemon`, `hearth_alive`/`call_hearth`/
`command_hearth` are `daemon_alive`/`call_daemon`/`command_daemon`, and
the dead `require_hearth` is dropped. The naming answer is yes on both
counts: `daemon` names the process and only the process, so it appears
in verbs and prose and in no file name; `ember` names the program and
every file it writes (`ember.db`, `ember.sock`, `ember.pid`,
`ember.log`), one stem and one rule, the shape `/var/run/docker.sock`
and `nginx.pid` already have. `<state root>/ember.sock` stutters because
the directory carries the name too; the stutter stays, because
`EMBER_STATE_ROOT` moves the four files out of that directory (a test
root is `<tmp>/ember-state`) and there the stem still says whose state
they are, while a `daemon.*` stem would split the folder into two
stems. One hazard came with the rename: a daemon built before it bound
`<root>/hearth.sock` and writes the same `ember.db`, so `daemon start`
now calls `retire_legacy(root)` first — it sends the old socket
`shutdown`, waits up to 5 s for that socket to stop answering, clears
`hearth.sock` and `hearth.pid`, carries `hearth.log` to `ember.log` (or
drops it when a current log exists), and refuses to start with exit 1
naming the pid file if the old daemon does not stop. Two writers on one
SQLite file is the law this daemon exists to keep, so the rename buys no
silent corruption. Tests: `ember/tests/test_flow.py` runs 213 checks,
three consecutive full runs, no paid call; a new `checks_rename` covers
the four file names, the absent `ember hearth` spelling, a dead
pre-rename socket and its pid and log, the exit-2 refusal of the old
verb, and a live fake pre-rename daemon that the new one refuses to
start beside. `ember/README.md` gains the stem rule in "Layout",
`rule-language.md` gains §0.8 and settles N29. N26 (the dismissal verb)
stays open.

**Round 30 (this session, owner).** Two asks, both code. First, the
round-29 `retire_legacy` is dead code — no space was ever run before
the rename, so no pre-rename daemon exists — and it is deleted: the
`LEGACY_*` constants, the `retire_legacy` function, its call in
`daemon start`, and the `path` parameter of `send_request`, the hook
only the retirement used. Second, N26 settles as (a) and lands:
`ember answer RID --dismiss` fails a waiting gate with no answer. The
flag takes no `--field` and no `-F` (both refused with exit 2);
`command_answer` routes `dismiss` through the daemon, and
`apply_answer` runs it after the manual-and-waiting checks, calling
`finish_failed` with `reason=dismissed` and then pump, closure, and
settle — the same tail the success path takes. So `run:RID.failed`
and `agent-type:LABEL.failed` carry `value=dismissed` (a rule selects
it with `--event agent-type:LABEL.failed=dismissed`), the root's tree
goes red, and the space settles instead of hanging; a loop rule keyed
on the verdict does not fire, because a dismissal writes the fault
verb, not the answer field. A dismissal of a done gate, of a model
run, or one carrying fields or text is refused with exit 2. The
manual briefing's closing instructions name `--dismiss`. Tests:
`ember/tests/test_flow.py` runs 230 checks — `checks_rename` loses
the five retirement checks and gains a `no legacy retirement` source
check, `checks_gate` gains the dismissal's unit arithmetic (the
model-run and fields refusals, the failed state and reason, both
fault atoms with `value=dismissed`, the re-dismiss refusal), and
`flow_gate` gains the CLI refusals plus an end-to-end dismissal (a
resubmitted job's gate dismissed, no restart, `space.settled` with
the new root in `red`) — three consecutive full runs, no paid call.
`ember/README.md` ("Human gates", the tests paragraph) and
`rule-language.md` (§4.15 B, §8 N26) carry the change. No commit.

## The name

A wisp is one small light. A ball of wisps is **an ember**: one body of
light, low and persistent, that dies to a glow and rekindles from ash.
The daemon that tends embers is **the hearth**; to wake a wisp is **to
stoke**; the urgent interrupt flag is **`--andon`**.

Runner-ups: **fen** (the marsh where wisps live; names the place, not
the ball), **lantern** (the vessel, not the space), **glow**, **skein**.

**Settled in round 2:** the owner accepted `ember` and put it in this
repository, `ember/` next to `wisp/` (Q1, Q5).

**Amended in round 29 (N29 b):** the process is **`daemon`**, not
`hearth`. The metaphor keeps the data — `ember` names the ball of light
and every file the program writes — and the role gets the plain word:
`ember daemon start|stop|status`. One name per thing, so no file is
named after a role.

## The core decision

**The coordinator is a python3 script, not a wisp.** Every mechanical
decision (membership, sequencing, delivery, cursors, slots, retries,
spawn) is arithmetic over rows; a model there adds latency and
non-determinism and buys nothing. Judgment stays outside the control
plane: a member that needs judgment asks another member with a
message, and the owner escalates to itself. **The warden is dropped
from the design (Q6: never).** No advisory layer exists, and no model
output changes routing, admission, or delivery.

Law: the log runs at filesystem speed and the engine never waits for a
model. Round 9 removes the last transport that could wait: the engine never
steers a live run. Round 10 adds one injection that waits for nothing: a
steer appends its inputs to a live run of the rule's target instead of
starting a second, and an agent's own `wisp steer` is data, not a routing
decision.

## Seam picks

| Seam | Pick | Why the losers lose |
|---|---|---|
| S0 packaging | standalone `ember`, stdlib, wisp via its CLI | a daemon inside a one-shot runner |
| S1 store | SQLite WAL, event-sourced, one writer | ack+cursor+slot must be one transaction |
| S2 placement | hearth daemon + unix-socket CLI | nobody fills a slot that frees with no daemon |
| S3 membership | record with id/agent/job, ended by `left`; no lease | leases evict live-but-idle members |
| S4 delivery | bodies ride `wisp steer --batch` as JSONL lines, the digest first in a hard wake; a **job** is hard when idle and held when live, a **steer** is hard when idle and soft when live; `wisp run` starts a run, `wisp steer` adds one | a body in the digest pays for itself on every wake; raw steers have no envelope; a note can wait for a turn that never comes |
| S5 addressing | bare names, `send` = my-space broadcast, `dm a,b,role:rev`; no `@`, no reserved word; bodies via `-F` only | topics add a second namespace; `@all` steals a legal name; argv bodies duplicate the file path |
| S6 governor | cap 3 + weighted fair share + aging; the account bucket binds before the model bucket | FIFO starves the second ember (the stated case); a per-model limiter misses a per-user meter |
| S7 spawn | hearth validates against policy; approval opt-in | free spawn is a fork bomb |
| S8 observation | CLI text + read-only SSE UI from one log | a second server for no gain |
| S9 recovery | at-least-once with a generic `wisp_steer_key` ack in `wisp.jsonl` | exactly-once reimplements wisp's commit |
| S10 authority | socket path 0700 (+ SO_PEERCRED later); peers are data, not authority | tokens add rotation for no gain on one host |
| S11 races | a run lock closes the two-run race; a steer lock closes the inbox rename race; a generic steer key heals a dropped message | a narrowed window is still a window |

Orthogonality holds except four named couplings: S4×S9 (the ack reads
the generic steer key), S4×S6 (a hard wake takes a slot), S2×S6 (no
daemon, no admission), and S4×S11 (v0 depends on the steer lock and
the run lock). S11 is not a seam; it is the audit that no seam left a window
open. **Round 8:** S3, S4, S5, and S9 die with the bus; S6 survives as cap 3
with pending actions, S7's admission becomes the run cap, S8 becomes
`query` plus the future UI, and S11 narrows to the run lock (W2) and the
steer lock (W1).

## Verified (no paid call)

| Round | Claim | Result |
|---|---|---|
| 1 | a killed run leaves an open segment | yes (`tool` tail) |
| 1 | `wisp continue` resumes it | yes |
| 1 | rewriting `wisp.run.json` before `continue` switches the model | **yes — the request carried the new model** |
| 1 | `wisp continue` drains the steer inbox | yes (`wisp_steered: true`, committed before the loop) |
| 2 | a constant-size wake prompt still delivers queued bodies | yes: the steered record precedes the prompt in `wisp.jsonl` and in the request |
| 2 | a stop-finish tail makes `continue` refuse and keeps the inbox | yes: exit 1, inbox present, then `wisp run` drains it (W4 raises this to 78) |
| 2 | a `wisp steer` can lose a line to the inbox rename race | **yes, reproduced with no model** (S11 R4) |
| 2 | one argv string caps at 128 KiB | yes: 130 KB passes, 200 KB dies with `E2BIG` |
| 3 | a `flock` in the steer writer and the intake closes the R4 race (test harness) | **yes: 50 runs, 0 losses** (S11 R4) |
| 4 | a queue of 3 steers plus the prompt costs one turn, not four | **yes: one POST carried all three steered records, in order, then the prompt** |
| 5 | a tool-timeout kill mid-stream, then `wisp steer` + `wisp continue`, resumes the run and delivers the steered ask | yes (falsifier-api child) |
| 6 | a 3-line JSONL batch piped to `wisp steer` without `--batch` lands as one steered record holding the raw JSONL text; the same three lines as three inbox lines land as three records; the current intake drops `key` | yes (fake endpoint): 1 record vs 3, `wisp_steer_key` absent in both |
| 8 | `nono run --rollback` + `nono rollback show <id> --json` gives a per-session change list `{path, type "+"\|"~"\|"-", size_delta}` over the granted paths; a revert shows nothing; two sessions on one tracked directory blur (the earlier-started session reported the other's write); `.git` is always excluded; no session id prints on exit | yes (nono v0.80.0, two probes; `rule-language.md` §3.7) |
| 8 | `wisp run --attach` stores images only (PNG, JPEG, GIF, WebP), so text inputs reach a run as paths in the prompt | yes (`wisp/wisp` 3426-3447, 1998-2000) |
| 9 | a stdlib Python snapshot diff over a per-run directory reports the exact set `del.txt -`, `mod.txt ~ +10`, `new.txt +`; 200 files, two walks, 16.5 ms | yes (`rule-language.md` §6.2) |
| 9 | `strace -ff -y -e trace=%file` around a run yields the operation and the resolved path (`openat(... "mod.txt", O_WRONLY\|O_CREAT\|O_APPEND) = 3</tmp/f7s/mod.txt>`, `unlinkat(... "gone.txt")`) with no privilege | yes; misses a write through a pre-existing mmap |
| 9 | `git worktree` plus `git diff --cached --name-status` gives exact `D`/`A`/`M` per worktree, one index per run | yes; needs a repo and a commit per run |
| 9 | a per-run namespace for an overlayfs upperdir is unavailable on this host: `unshare -Ur -m` fails `EPERM` on `uid_map`, `bwrap` fails "setting up uid map: Permission denied" | yes; overlay, fanotify, and bpftrace are out for want of privilege |
| 9 | `<environment>` is baked into the first system record with the absolute `SESSION DIR`, the creation time, the model, and the thinking (`new_session` 209-240; a real session record shows it) | yes; a verbatim fork would make every run believe it lives in the type dir, so round 9's answer was a rewrite and round 10's is W13, a render |
| 10 | `wisp.jsonl` records carry no timestamp field, so the creation time exists nowhere but the baked block; W13 must store `created` in `wisp.run.json` | yes (the session-014 log and `wisp.run.json` both show it) |
| 10 | `strace -ff -y` with a curated syscall set around `bash -c 'touch x; python3 tool.py'` reports the read of `~/.config/research/cfg.toml`, the append to a source file outside the work dir, the create of `out.md`, and the delete of `gone.txt`, over 18 pids, with no privilege | yes (strace 6.8) |
| 10 | the curated set costs 0.32 s and 0.66 MB on one `python3 -c pass`, against 0.51 s and 2.3 MB for `%file`; the floor is 9 ms per traced process on `/bin/true` | yes (8 runs each, this host) |
| 10 | `unlink("gone.txt")` carries no resolved path, so a per-pid cwd tracker is needed; `chdir` and `getcwd` are traceable and resolve the relative delete | yes (the same probe; `getcwd` returns the absolute path) |
| 10 | `strace -ff -y` passes the traced program's exit status through: `bash -c 'exit 75'` reports 75 and `kill -TERM $$` reports 143, so W4's table still holds over the wrapper | yes |
| 14 | a steer fired ~0.4 s after a first, while the target row is `live` but `wisp.run.lock` is not yet held, starts a duplicate run instead of joining: the dispatch returns at +0.856 s with state `live`, the lock is first held at +1.218 s, and `run_is_live` on a `live` row requires the held lock; at ~0.55 s between steers the join succeeds | yes (fake endpoint, no paid call; `test_flow.py` fails the three steer checks 4/4) |
| 15 | keeping a spawned run `starting` and promoting it in `Hearth.poll` closes the steer-join window | yes: `ember/tests/test_flow.py` 34/34, three consecutive full runs, `flow_steer` among them |
| 15 | `ATOM_RE` parsed `agent-type:distiller.handoff=true` as verb `handoff=true` with no op, so no comparison event in `--event` could ever fire | yes: the stored rule row shows `"verb": "handoff=true"`, `"op": null`; the verb class `[^.=<>!]+` fixes it and the recipe's `=true` row fires |
| 15 | the round-13 recipe runs end to end | yes (`flow_exhaust`, no paid call): worker failed `reason=wallclock`, distiller done, worker done under the distiller, `agent-type:worker.ready`, `agent-type:worker.done`, then `space.settled` |
| 16 | the recipe's no-go loop runs end to end and the cap blocks the fourth restart | yes (`flow_loop`, no paid call): 4 worker runs and 4 critic runs, all `done`, 4 `agent-type:hand.ready`, 4 `agent-type:critic.approved`, `rule:loop.capped`, closure `agent-type:hand.done`, `space.settled` with empty `red`; each restart's parent is the critic run |
| 16 | a rejected job settles green, not red | yes: `.done` is `tree_ok` over finished runs, and `tree_ok` reads states only, so the fourth no-go still closes the tree; the README's red claim was wrong and is corrected |
| 16 | `wait_settled` could return in the gap between a finished run and the firing of its atom | yes: `flow_success` saw one run of two once; requiring `space.settled` as the newest atom fixes it (46/46) |
| 17 | `--out` accepts any `CATEGORY:VALUE` and injects only `VALUE` as the work-dir path, so `answer:answer.md` is a cell named `answer:answer.md` with work path `answer.md`; two categories with one value bind two cells to one file | yes (source read: `cell_ok` 321, `parse_cells` 330, briefing 786, `contract_problems` 1264) |
| 17 | every run forks `agent-types/<type>`, so a same-session distill run needs an origin branch: `prepare_run_dir` 1166 would fail `agent type not found` for a derived label | yes (source read: `prepare_run_dir` 1161) |
| 18 | `wisp continue` reads no stdin and appends no prompt; the prompt-bearing continuation is `wisp run -d <the same dir>`, and wispy's distill turn is exactly that call with no guard | yes (source read: `wisp/wisp` `run_agent_loop` 1146-1180, `continue_agent_loop` 1181-1214; `wispy/wispy` `SessionService.run` 495-503, `distill` 858-899) |
| 18 | a fork copies `wisp.jsonl`, `wisp.run.json`, `wisp.modelcfg`, and an empty `wisp.usage`, sets a fresh `created`, takes `-m`/`-t`, and refuses a busy source with exit 76 | yes (source read: `wisp/wisp` `fork_session` 1218-1285) |
| 18 | a result row lives in the run's session dir, and both the writer and the reader use it, so two run rows over one session dir read each other's fields | yes (source read: `ember/ember` `command_result` 2184-2239, `results_of` 1220-1240, `finish_run` 1428-1429) |
| 18 | `prepare_run_dir` returns early when the run dir exists, so a resume in the source dir needs no fork step | yes (source read: `ember/ember` `prepare_run_dir` 1161-1183) |
| 18 | `--context-guard` percent mode refreshes `wisp.modelcfg` from `WISP_LLM_MODEL_INFO_FILE` before failing, so `70%` works on a fresh fork that has no modelcfg yet | yes (source read: `wisp/wisp` `context_guard_of` 1719-1752, `refresh_model_cfg` 3505-3529) |
| 19 | a `--guard 100` rule stops at the first round boundary with exit 75 and reason `guard` when the endpoint reports 1234 prompt tokens on the round's final chunk | yes (`flow_guard`, no paid call): the failed run, then the `--resume` distill in the same dir, then a fresh continuation, and the `agent-type:hand` fault atom carries `value=guard` |
| 19 | a `.resume` run shares the source dir and work dir, and the per-run result filter hides the source's fields | yes (`flow_guard`): the failed row's results are `{ready}` and the resumed row's are `{handoff}`, over one `results.jsonl` |
| 19 | a `.fork` run gets its own dir and work dir, seeded from the source, with `-m`/`-t` applied | yes (`flow_fork`): the fork's `wisp.run.json` holds `model=fake2 thinking=low`, `partial.md` is in both work dirs, and `handoff.md` is only in the fork's |
| 19 | the README recipe's five rule rows are accepted as written | yes (scratch space): `pickup`, `review`, `loop`, `rescue`, `continue` with `--guard 70%`, `--wallclock 1800`, `--model`, `-F rescue.md` |
| 19 | a refused argument reached the caller as `error: 2` | yes, before the fix; `EmberExit` carries the message, so `--out answer:x.md` now answers `--out takes session-file:NAME or resource:NAME, not answer` |
| 20 | the round-19 rescue cap `handoff<3` never blocks a failing distill | yes (source read: `finish_failed` writes no handoff, `count_cap` counts atoms, and a failing resume inherits the worker type and writes `agent-type:worker.failed`), so each failing-distill cycle adds no handoff and rescue fires unbounded; the corrected budget is `--cap 'agent-type:worker.failed<4'`, one fresh failed atom per firing, exactly three firings |
| 20 | a bare `--event agent-type:worker.failed` matches every reason | yes (source read: `conjunct_matches` on a fixed verb with no comparison returns true regardless of value), so one rule covers wallclock, guard, exit, crash, and contract failures |
| 20 | `ember query run:<rid>` prints the stored failure report | yes (source read: `print_run` appends `meta_get("report:<rid>")`, and `--json` carries it as `report`), so a reviewer persona reads a failure with bash and no engine change |
| 20 | `--run agent:pickup` on the handoff event yields the same tree as `--run .parent` | yes (source read: `infer_parent` takes the lowest common ancestor of the trigger runs — the resume run — for a type target, and `.parent` names the same type the agent names), so the split changes no tree fact |
| 21 | `--cap 'agent-type:reviewer.approved<4'` parses as expression `agent-type:reviewer.approved` with threshold 4, and `count_cap` counts matching atoms space-wide; `--cap 'agent-type:worker.failed=guard<3'` carries the value test inside the count | yes (`ember/ember` `parse_cap` 346, `count_cap` 633; a direct probe) |
| 21 | the same string in `--event` matches both `approved=true` and `approved=false`, because bool atoms are coerced to int, while `agent-type:worker.failed<4` never matches a string reason | yes (probe of `conjunct_matches` 561: `int(True)=1`, `int(False)=0`, both `< 4`; the reason case returns False) |
| 21 | a `cells` row carries the writing run, so `.out` can be resolved against the trigger run; `briefing_of` ignores it and takes `latest_cell` | yes (source read: the `cells` schema has `run TEXT` at 198-206, and `briefing_of` 828-895 calls `latest_cell(source_outputs[0])`) |
| 22 | the bare cap is refused and the wrapped form parses both with and without a value test | yes (probe of `parse_cap`): `agent-type:reviewer.approved<4` and `agent-type:worker.failed<4` exit 2 with `--cap needs count(EXPR)<N`; `count(agent-type:reviewer.approved=false)<4` yields expr `agent-type:reviewer.approved=false`, n 4, atom op `=`, value `False`, kind `bool`; `count(agent-type:worker.failed=guard)<3` yields a str atom |
| 22 | type-strict matching splits the two grammars | yes (probe of `conjunct_matches`): a bool atom `approved` gives False for `<4`, `=4`, `=false`, `!=true` and True for `=true`; an int atom `defects=6` gives True for `>5` and False for `>6`; a str atom `failed=guard` gives True for `=guard` and False for `<4` |
| 22 | `count_cap` counted `me` and `id:` as zero before the fix | yes (source read: it queried the literal subject `id:X`, which no atom carries, and returned 0 for `me`); it now resolves through `target_subjects` with the rule |
| 22 | a hearth-side refusal reached the caller as exit 1, whatever the argument error | yes (`ember rule add --cap 'agent-type:hand.ready<4'` answered the message with exit 1); the answer now carries `code` and the client exits 2 |
| 22 | the suite passes with the wrapper | yes: `ember/tests/test_flow.py` 125/125, no paid call, including `checks_cap` (19 checks: grammar, type-strict match, the declared-type refusal), the refused bare cap in `flow_loop`, and the four no-go atoms counted by value |
| 23 | a rule can read the triggering run's answer with no flag: the verifier's briefing carries `answer: run <designer id> (designer)` and the text the model wrote | yes (`flow_success`, no paid call): the answer block, `ember query run:<id> --json` with `answer`, and no `session-file:` cell in `space show` |
| 23 | a run cut by a wallclock has no answer, and the next briefing says so instead of failing | yes (`flow_exhaust`): the distiller's briefing carries `answer: none (run <failed id> (worker) ended with no final message)`, and the continuation's briefing carries `answer: run <distiller id> (distiller)` |
| 23 | `--out` is refused as an unknown flag and `--in .out` is refused with a message naming the default | yes: `ember rule add ... --out session-file:x` exits 2 with `--out` in stderr; `--in .out` exits 2 with `by default` in the refusal |
| 23 | the answer reader, the clip, and both contract reasons work without a hearth | yes (`checks_answer`, 9 checks): last non-empty assistant text wins over an earlier text-plus-tool-call record; a 16 KiB clip keeps the head, names `ember query run:`; an empty log is `no_response`, a missing declared field is `no_result`, and an answered run with its field passes |
| 23 | the whole suite passes after the drop | yes: 141/141, three consecutive full runs, no paid call |
| 24 | `maybe_settle` counts `NONTERMINAL` runs and `admit` counts `LIVE_STATES` runs, so a state in `NONTERMINAL` only blocks settlement and closure and holds no cap slot | yes (source read: `maybe_settle` 1681, `admit` 1367, `live_runs` 660, `LIVE_STATES` 50) |
| 24 | `tree_settled` and `tree_ok` read the `runs` table only, so a gate that is not a run row is invisible to closure and the root's `.done` fires before a human answers | yes (source read: `tree_ok` 1004, `tree_settled` 1015) |
| 24 | `wisp_lock_free` treats a missing dir as a free lock and `reconcile` crash-fails every non-terminal row whose lock is free, so a dirless waiting row must be excluded from `reconcile` | yes (source read: `wisp_lock_free` 1976, `reconcile` 1995) |
| 25 | the cap is per-space: `admit(limit=CAP_DEFAULT)` counts `live_runs(conn)` on one space's `ember.db`, the socket is `<space>/hearth.sock`, the db is `<space>/ember.db`, and no cross-space state exists, so two hearths give six concurrent runs against Q2's constant 3 and the Goal's shared cap | yes (source read: `admit` 1366, `socket_path` 2007, `db_path` 104) |
| 25 | the per-space scope is an implementation accident, not a decision: round 12's gate was "v0 is one space end to end", no round decided a per-space cap, and round 24's README line "there is no single global daemon" restated the implemented shape | yes (ticket rounds 12 and 24; `ember/README.md` "Why a hearth") |
| 25 | a spawned run carries no `PDEATHSIG` and no session tie beyond `hearth.track`, so a hearth death orphans the run to init, the run keeps its lock, and `reconcile` adopts it at restart: the blast radius of a global daemon restart is a pump/poll pause, not lost work | yes (source read: `spawn_run` 947, `reconcile` 1995) |
| 26 | read verbs open `<space>/ember.db` read-only directly and mutating verbs go through the socket, so one DB changes only the read path's file resolution, from the space dir to one fixed path | yes (source read: `open_read` 2346 opens `db_path` with `mode=ro`; `call_hearth` 2357 carries `submit`, `rule add/disable`, and `steer`) |
| 26 | the hearth loop is single-threaded — one accept, one dispatch, then `hearth.poll`, all on one connection — so one DB has exactly one writer and the one-writer law holds unchanged | yes (source read: `serve` 2228) |
| 26 | `atoms.seq` is `INTEGER PRIMARY KEY AUTOINCREMENT` per file, the fixed `meta` keys `settled`, `report:<rid>`, `closure:<root>` carry no space, and cell names are user-chosen, so one DB globalizes the seq and collides `settled` and cell names across spaces; run ids (`r-` + 3 random bytes, collision-checked in the store) stay unique in one file | yes (source read: SCHEMA 127-216, `new_run_id` 676, `meta_set` 472) |
| 27 | the registry and the new verbs work end to end with no paid call: `ember hearth start` needs no space, `space init` registers (`registered <path> as s-<hex>`), `space list` prints id, path, active/paused, created, `space export -o FILE` writes the nine-table JSON, a mutating verb with no hearth answers `the hearth is not running; run ember hearth start` with exit 1, and `space show` on an unregistered path answers `no space at ... (run ember space init)` with exit 2 | yes (manual smoke, `EMBER_STATE_ROOT` in a tempdir) |
| 27 | two spaces on one hearth share nothing but the daemon and the cap: ga's run is invisible to gb's `query runs` and `query run:<rid>` (exit nonzero), gb holds no atoms, the same rule id `pickup` and type name `hand` exist in both, and `space export` of ga carries only ga's rows | yes (`flow_global`, no paid call) |
| 27 | the cap counts live runs across every space: four hanging jobs over two spaces, both paused while the jobs land and unpause d-then-e, fill three slots and park the fourth (`starting+live=3`, `pending=1` right after the unpause), and the parked run starts when another space's run fails; all four end `reason=wallclock` and both spaces settle | yes (`flow_global`, no paid call) |
| 27 | `next_pending` alternates the spaces round-robin (a, b, a, b over four picks), never picks a paused space, and `live_runs_all` counts rows across spaces (4 over two); `meta_set` on one space leaves another's key None | yes (`checks_global`, in-memory store, no hearth) |
| 27 | the whole suite passes on the global daemon and the one database | yes: `ember/tests/test_flow.py` 166/166, three consecutive full runs, no paid call |
| 28 | a `human:` rule opens a waiting run with no dir and no process: the row is `mode manual`, state `waiting`, `dir` and `workdir` empty, `started` set at creation, the question body riding the briefing | yes (manual smoke and `flow_gate`, no paid call) |
| 28 | `waiting` is open work but no slot: `maybe_settle` refuses to settle while it waits, `live_runs_all` counts zero, `admit` never picks the row, and `ember why` lists it under `waiting:` | yes (`checks_gate`, `flow_gate`) |
| 28 | a hearth restart leaves a dirless waiting gate waiting: `reconcile_space` excludes the state `waiting` and `mode manual`, where a free lock on a missing dir would crash-fail it | yes (`flow_gate`: hearth stop, start, the same waiting row) |
| 28 | `ember answer RID --field F=V -F FILE` completes the gate through the unmodified `finish_success`: atoms `agent-type:LABEL.FIELD` with typed values and `run:RID.done`, the answer text stored on the row and printed by `ember query run:RID --json`, the space settling green only after the human spoke | yes (`flow_gate`) |
| 28 | the reviewer loop runs with a human in the chair: `--event agent-type:confirm.approved=false --run hand` restarts the worker under the gate, and the restart's briefing carries `answer: run <gate> (confirm)` plus the reject text | yes (`flow_gate`) |
| 28 | the refusals exit 2 with named messages: a bad bool, a missing required field, an unknown field, `result set` on a manual run, a re-answer of a done gate, `--guard`/`--wallclock`/`--model`/`--thinking` on a `human:` target, a bodyless human rule, and a bad label | yes (manual smoke and `flow_gate`) |
| 28 | the whole suite passes with the gate | yes: `ember/tests/test_flow.py` 202/202, three consecutive full runs, no paid call |
| 29 | the daemon's name is one name per thing: `ember daemon start|stop|status` runs the one process, `ember hearth start` exits 2 from argparse, `Hearth` is `Daemon`, and the dead `require_hearth` is gone | yes (`checks_rename`, plus a manual smoke: `ember daemon status` answers `daemon stopped in ~/.local/state/ember` with exit 1) |
| 29 | the state root holds `ember.db`, `ember.sock`, `ember.pid`, `ember.log` and nothing named after a role | yes (`checks_rename`, and `ember daemon start` creates `ember.sock` and `ember.log`) |
| 29 | a dead pre-rename socket, pid, and log are retired by `daemon start`: the old files are removed and `hearth.log` becomes `ember.log` | yes (`checks_rename`: a bound-then-closed socket, `hearth.pid` 999999, and a log file) |
| 29 | a live pre-rename daemon blocks the rename instead of racing it: `daemon start` exits 1 with `from before the rename` and names the legacy pid file | yes (`checks_rename`: a fake server that answers every request, no paid call) |
| 29 | the whole suite passes after the rename | yes: `ember/tests/test_flow.py` 213/213, three consecutive full runs, no paid call |
| 30 | `retire_legacy` is gone with its trappings: no `LEGACY_*` constants, no `path` parameter on `send_request`, no call in `daemon start`, and `checks_rename` asserts the string is absent from the source | yes (source read, `checks_rename`) |
| 30 | `ember answer RID --dismiss` fails a waiting gate: state `failed`, `reason=dismissed`, fault atoms `run:RID.failed` and `agent-type:LABEL.failed` with `value=dismissed`, no restart of the worker, and `space.settled` carries the dismissed gate's root in `red` | yes (`checks_gate`, `flow_gate`, no paid call) |
| 30 | the dismissal refusals exit 2 with named messages: `--dismiss` with `--field` or `-F`, a dismissal of a model run, of a done gate, and one carrying fields through the socket | yes (`checks_gate`, `flow_gate`) |
| 30 | the whole suite passes after both changes | yes: `ember/tests/test_flow.py` 230/230, three consecutive full runs, no paid call |

The model-switch row contradicts kodama's design note that a
guard-stopped session cannot change its model pair. Round 5 keeps the
fact but changes the mechanism: ember retries a rate-limited member on a
fallback model through `wisp fork`, so the source session stays intact.

## Gap decisions

26 gaps are decided in `design-options.md` §7. The load-bearing ones:

- A wisp has no sleep, so a sleeping member is a record with no live
  run; a wake costs a turn.
- The merge window and TTL are mandatory, or a broadcast is a token
  amplifier. A steer joins a live run at no extra turn; a job is held
  while the member is live. `wisp` already turns N queued messages into
  one turn (verified round 4), so a message burst needs no turn-batching.
  The run-saver is the merge window in the hearth's `admit()` (Q8); the
  digest frames the burst and never carries a body.
- One live run per member session dir is a data-integrity law. Two
  members of one agent type have different dirs and run concurrently.
- The member id is durable; the session is an epoch; the pid is a
  moment. A distill preserves the id and the job.
- Delivery is acknowledged by a generic `wisp_steer_key` on a steered
  record in `wisp.jsonl`, never by an exit code.
- A body arrives only through `-F FILE` or `-F -`. A job is a file.
- A spawn names one agent definition and one job file. The definition
  names a route type; an external `llm_route <type>` names the model.
- A guard 75 distills at once. A fallback model uses `wisp fork`, not a
  private `wisp.run.json` rewrite. **Round 18: the guard writes the fault
  atom; a `--resume` or `--fork` rule runs the distill turn, so the engine
  distills nothing by itself.**
- A message is immutable. There is no ephemeral steer and no compaction.
- Rate limits bind on the account before the model; the account bucket
  is a fraction of the provider limit, and a 429 is the ground truth.
- A body never enters the digest; the digest holds roster, ids, counts,
  and a 120-character excerpt (2 KB typical, 12 KB hard). A body over
  2 KB is a pointer, so a handoff costs the reader one tool call and
  nothing when unread.
- A send resolves only inside the sender's space, and no syntax reaches
  another space. A member that joined both spaces is the only
  cross-space carrier, and both logs show the two rows.
- Delivery bodies ride `wisp steer --batch` JSONL lines. A hard wake is
  the batch plus `wisp run` with a constant trigger; the run drains the
  inbox first. A **job** never joins a live run: it is held until the
  run ends, then a new run starts. A **steer** joins a live run as soft
  delivery, and hard-wakes an idle member. A wrong liveness guess costs
  one retry, never a message.

**Round 8 voids these bullets** (the source is the owner's message,
reviewed in `rule-language.md` §1.3 and §6): the merge window (Q8), TTL,
the digest, delivery classes, the `wisp_steer_key` ack, `wisp steer
--batch`, and the member roster. What replaces them:

- A start is a process the engine owns, not a delivery. The run row, the
  run lock (W2), and the typed result are the record; no ack exists.
- A rule is an atom expression plus a typed edge: agent, input
  references, output declarations, cap. Atoms are append-only; each rule
  consumes the atom ids it binds, once per rule.
- A cell is a named, versioned pointer in the space. ~~`--out` injects
  the path; a missing declared output fails the run.~~ **Round 23: no
  rule declares an output; a run's answer is the delivery, and the space
  owns only `task:` and `steer:` cells.**
- The only steer is the user's. It is an atom (`space.steer`) plus a
  rule plus a steward agent. A live run is steered by a conditional
  engine action that holds the run lock.
- Rules live in two scopes only: a root library and the space.

**Round 9 amends the last two bullets.** The owner's answers:
`--require FIELD:TYPE` makes a result field a verb and a verb may carry
one comparison test; `--cap` counts atoms, not firings (round 22 spells
it `count(EXPR)<N`); the engine never steers a live run, so `ember
steer` writes an atom and starts a steward run; a restart re-declares its
inputs and outputs; the
root library is out of v0, so every space evaluates only its own rules;
an agent type is a wisp session directory and a run is a `wisp fork` of
it; ~~a declared output is checked for existence and for change against
the latest cell version~~ (void in round 23: `no_response` checks the
answer and `no_result` checks the fields); and the change list comes from
a per-run working directory, not from nono. F5 is
accepted, so recovery is concrete: one committed log per space, a start
that writes the run row and `run:<id>.started` in one transaction before
the spawn, and a startup scan that turns a non-terminal run with a free
lock into failed with `reason=crashed` and adopts any run whose lock is
held (`rule-language.md` §4.10). The Y1 vocabulary stands:
`space.steer`, `space.settled`, `run.started`, and `rule:<id>.capped`
are valid atoms.

**Round 10 amends four of them.** "The only steer is the user's" gains
one exception: a steward run, being a model with bash, may `wisp steer`
a live worker. The engine has one injection and no other: a firing whose
trigger atoms include `space.steer` appends its inputs to a live run of
the rule's target instead of starting a second (`rule-language.md`
§4.8). "The change list comes from a per-run working directory" is
replaced by syscall capture: `strace -ff -y` with a curated set wraps
every engine-started run, so a write outside the work dir and a read of
`~/.config` are visible, and the work dir stays for the run's own files
(§6.3; round 23 drops declared outputs). A run now has a parent and a tree: `agent-type:T.done` is the
closure of a root's whole tree and `agent-type:T.failed` stays a per-run
fault (§4.11). And `<environment>` becomes a request-time view (W13), so
`wisp fork` copies records instead of rewriting one (§4.7).

## Build order

**Round 10 sets the order's contents and its gate.** v0 is one space end
to end: the store, the hearth, `space submit`, rule rows with `--event`,
`--require`, `--in`, `--cap`, and `--id` (round 23 drops `--out`: the
answer is the delivery), atom consumption, cells with versions, typed results, the parent tree with both closure
atoms, the named failure report, per-run work dirs, syscall capture over
a curated syscall set, two-phase start with admission, cap 3, `ember
why`, `trigger show`, `query`, and crash reconciliation. Round 12 lands
v0 and the nine wisp changes; the order put W13 first because W7 depends
on it: W13, W11, W7, W2, W4, W5, W1 (lock only), W10, W12. v1 adds
grants and per-type slots, both deferred in round 9 → v2 the steward,
the steer join, and the `ember steer` path (the steward is an ordinary
rule-driven type, not a conditional steer) → v3 the `--resume` and
`--fork` targets with the `--guard` and `--wallclock` flags → v4 UI.

**Round 18 amends v3:** the targets are `--run TYPE`, `--run .parent`,
`--resume`, and `--fork`, with `--guard` and `--wallclock` as rule
options; the resource store is dropped, because the prompt is the rule's
body. v3 lands the three targets, the per-run result rows, and the two
policy flags, and no engine default (N10 b). The separate distiller type
remains a `--run` shape. **Round 19 lands v3** in `ember/ember`, with
`--model` and `--thinking` on the rule row and the `session-file:` /
`resource:` output split. **Round 27 amends the v0 substrate**: one
global hearth and one database for all spaces replace the per-space
daemon and per-space `ember.db` (N27 a, N28 a); everything above them —
rules, atoms, cells, trees, steers — stays per-space and unchanged. v1
(grants, per-type slots), v2 (the steward
type), and v4 (the UI) remain. **Round 28 lands the N25 (b) human
gate** on the round-27 substrate: `--run human:LABEL`, state
`waiting`, and `ember answer`; the dismissal verb is N26. **Round 29**
renames the daemon verb and the state-root files (N29 b) and moves no
build-order item: `--run human:LABEL`, the three targets, the rule
flags, and the one hearth all stand, now spelled `ember daemon start`.
**Round 30 lands the N26 (a) dismissal** (`ember answer --dismiss`)
and deletes the round-29 `retire_legacy` retirement as dead code.

The round-8 and round-4 orders are kept in `wisp-changes.md`'s log. The
warden is out (Q6: never). **Round 18:** a guard 75 writes the fault atom;
a `--resume` or `--fork` rule runs the distill turn, so the engine
distills nothing by itself. A fallback model uses `wisp fork` by hand;
whether a `--fork` rule carries `--model` is N18.

## Wisp changes

The detailed plan is `wisp-changes.md`. Round 12 implements the nine
required changes in `wisp/wisp`, covered by `tests/test_wisp_changes.sh`.
That file lists the nine required changes and keeps every rejected or
superseded one in a log at the end.
The status table:

| # | Change | Status |
|---|---|---|
| W0 | `wisp send` + `wisp.prompt.md` + trigger + key | **withdrawn by the owner (round 4)** |
| W1 | steer lock (`flock` on the append and the intake) | accepted in round 4, shrunk in round 8; round 9 dropped it; **round 10: required again, lock only** — the engine's joined steer and a steward's own `wisp steer` are two writers on one inbox, and the rename race is reproduced. No `--batch`, no `--key`, no `--ttl-s` |
| W2 | run lock, typed busy exit | accepted; **round 8: promoted** — the lock is the liveness record |
| W3 | `wisp resume` | dropped; `continue` covers it |
| W4 | exit table + machine line | accepted |
| W5 | `wisp status --json`, including committed keys | accepted; **round 8: `committed_keys` drops** |
| W6 | ack index | **dead in round 8**: no ack exists |
| W7 | `wisp fork` | replaced `wisp model set` in round 4; **round 10: required, and simplified** — a run is `wisp fork <type dir> -o <space>/runs/<rid>`, the fork copies `wisp.jsonl` and `wisp.run.json` with a fresh `created`, and no record is rewritten, because W13 renders the `<environment>` block at request time |
| W8 | `wisp compact` | dropped; use the `wispy` distill recipe |
| W9 | ephemeral steer | rejected; messages stay immutable |
| W10 | `--no-stream` | accepted |
| W11 | `wisp new -d DIR` / `--from` | `-d` accepted, `--from` dropped; **round 9: required, and `DIR` is the parent directory** — a type is `wisp new -d <space>/agent-types --name <type>`, which today fails because `new` has no `-d` (`wisp/wisp` 1792, `SESSION_DIR_COMMANDS`) |
| W12 | `--wallclock` | accepted, on `run` and `continue` |
| W13 | request-time `<environment>` | **new in round 10, required, and first in the build order**: the block is a view rendered from `wisp.run.json` and `-d`, never a record; `--env-in-system-prompt` moves its effect to request time; a legacy baked block is stripped and re-rendered. **Round 11:** the switch's carrier is N9; the block is rendered once per request, before the earliest record that carries the marker |

**Round 10:** the required set is W1 (lock only), W2, W4, W5, W7, W10,
W11, W12, and W13. W13 lands first, because it turns W7 into a plain
copy. W1 returns because two processes reach one inbox: the engine's
steer join and a steward's own `wisp steer`. The transport is a start
plus that one declared exception, so the round-4 transport map is
superseded and lives in `wisp-changes.md`'s log.

Boundary: rules, cells, caps, admission, the parent tree, the steward,
the syscall parse, and the UI stay in ember. `wisp` exposes facts and
mechanisms; policy never enters `wisp`. A change earns its place only
when `wisp` already owns the file, the format, or the process, and the
change removes a duplicate implementation or closes a race.

## Gaps

The design and the API contract are updated; round 12 writes v0 and the
nine wisp changes. Round 9 answers the thirteen language axes and the
eight findings, so the
language questions Q35-Q42 and Q44 settle and the rest die with the bus.
Round 10 answers Q43 and adds five rows. Round 11 adds N9 about
the environment switch. N9 settles in round 12. Round 13 adds N10-N13 about
exhaust-and-continue. Round 17 adds N14-N17 about cell categories, resource
storage, the distill surface, and the guard. N10 settles in round 17 as (b).
Round 18 settles N11, N12, N15, N16, and N17 on the owner's three targets
and two rule flags, and adds N18 and N19. Round 19 settles the last four:
N13, N14, N18, and N19, and lands v3. Round 20 adds N20-N22 about the
agent/rule split, the event disjunction, and the failure report as an
input. Round 21 adds N23 about the cap spelling and corrects N20's
`--in` to extend. Round 22 settles N23 and lands the `count(...)` wrapper.
Round 25 settles N25 as (b) and adds N27 about the daemon's scope.
Round 26 adds N28 about the store's scope, coupled to N27: one SQLite
file for all spaces requires the global hearth. Round 27 settles N27
and N28 together and lands both in `ember/ember`. Round 28 lands the
N25 (b) human gate and adds N29 about the daemon's name. Round 29
settles N29 as (b), the rename, and lands it. Round 30 settles N26 as
(a) and lands it. Eighteen stay
open, all about the language and the wisp plan: Q7, Q15,
Q17, Q18, Q19, Q31, Q33, N1-N8, and N20-N22, with N1
subsumed by N20 if the split is accepted. Round 23 adds N24 about
`--out` and settles it.

| # | Question | Options | Rec |
|---|---|---|---|
| Q7 | What is the account token budget per minute, and does ember take half of it? | (a) `0.5 ×` the provider limit; (b) measure for a week, then set it; (c) no budget, react to 429s only | b, then a |
| Q15 | Is `ember tail` needed? | (a) drop it; the UI streams; (b) add `log --follow`; (c) keep `tail` | a |
| Q17 | What is the router contract and fallback shape? | (a) one JSON line with `model`, `thinking`, `fallback`; (b) two commands; (c) plain text lines | a |
| Q18 | Which wall clock wins when a run has several pending atoms? | (a) minimum; (b) first; (c) the type only | a |
| Q19 | Distill in the same session, then start a new session? | (a) yes, the `wispy` recipe; (b) distill in a new session seeded with `render-past`; (c) other | a |
| Q31 | Is the review-before-commit gate a rule or a gate the engine enforces regardless of rules? | (a) rule; (b) hard gate; (c) both | c |
| Q33 | Claim seam for cross-space exclusivity: defer and keep `claim` in the action set, or design now? | (a) defer, keep the action; (b) design now | a |
| N1 | `--require` is a rule flag, so two rules over one type can demand different fields and the engine cannot notice. Does the type carry a default field set a rule may extend? | (a) rule only; (b) type default, rule may add; (c) type only | b |
| N2 | What is the cap counter's scope? The F1 expression has no scope word. | (a) the whole space; (b) the `--id` ancestor; (c) the rule | a |
| N3 | Is a fixed cell name acceptable now that `{trigger}` is out? A per-run output needs a distinct cell per rule. | (a) yes, distinct cells per rule; (b) return `{trigger}`; (c) the agent picks the name | a |
| N4 | Is `agent-type:T.done` root-scoped (once per submitted job) or fired by every run of T whose subtree is green? | (a) root only; (b) any run of T | a: `id:` already sequences a decomposition, and a nested `.done` double-fires a rule keyed on the type |
| N5 | Raw trace retention: delete after the parse on success, keep a window, keep everything? | (a) delete on success, keep a failed run's trace; (b) seven days; (c) keep all | a, at 0.6 MB per tool call |
| N6 | Is a steer's join kind-scoped (any `space.steer` rule joins a live target) or steward-only? | (a) kind-scoped, needing no flag; (b) steward-only, needing a type special case in the engine | a: the atom's subject decides, and the engine never has to know a steward from a worker |
| N7 | Does `wisp new -d DIR` create missing parents? | (a) yes; (b) fail unless `DIR` exists | a: `<space>/agent-types` may not exist yet |
| N8 | Does `--env-in-system-prompt` default on for a session made with `-s`? | (a) keep it opt-in; (b) default on | a: changing the default changes every prompt, and the flag already works |
| N9 | Does the environment switch live on `wisp new` or on `wisp build-system-prompt`? | (a) on `build-system-prompt`: `--record` (alias `--wisp-jsonl`) emits the system record, `--include-env` sets `include_env: true`, `new -s` stores bytes, `-s` takes a JSON object with `"type": "system"` as a record and any other bytes as text, `wisp.run.json` keeps `created` and `project_dir`, `sessions_root` derives from `-d`'s parent; (b) keep the switch on `new`, store `env_in_system_prompt` in `wisp.run.json`, render at request time; (c) accept the switch on both, one marker | a: `new` stops composing text, one composer exists (`build-system-prompt`), the marker travels with the record through `fork`, and the `-s`-without-env error path (`wisp/wisp` 1928) disappears |
| N10 | Is distill-and-continue an engine default or a rule pattern? | (a) engine: on 75/124 run a distill turn with no guard, then start a fresh fork of the type seeded with the handoff, keeping the job and the cap; (b) space rules: a distiller type plus `rescue` and `resume` rows, as in `ember/README.md`; (c) both: the engine arms the guard and writes a typed `run:<id>.exhausted` atom that a space rule consumes | **settled in round 17: (b)**, the owner prefers a rule to an engine default; the round-17 shape is a `--distill RESOURCE` row plus a `--run .parent` restart row; a is dropped |
| N11 | Where does the context guard value come from? | (a) `EMBER_CONTEXT_GUARD`, default off so no space changes behavior; (b) default `150k` tokens; (c) a per-type field on the rule or in `wisp.run.json` | **settled in round 18 as (c), the rule flag `--guard LIMIT`**; the env default is dropped, the percent form resolves in wisp from `wisp.modelcfg`, and `rule add` checks only the form |
| N12 | What is a continued run's identity? | (a) a new run row whose parent is the exhausted run; (b) the same run row re-pointed at a fresh fork dir; (c) the same dir resumed with `wisp continue` and a larger guard | **settled in round 18 as (a) with (c)'s mechanism**: a new run row over the same session dir, started with `wisp run -d <the same dir>` and the rule's prompt, so the log stays immutable and the tree records the epoch chain |
| N13 | Does a wallclock stop check the contract before failing? | (a) no, distill first; (b) yes, a written output plus set fields counts as success | **settled in round 19: (a)**, stated flat: a wallclock stop is a failure, period; `finish_run` tests exit 124 before the contract |
| N14 | Is `--out` restricted to the `session-file:` category? | (a) yes, `rule add` refuses any other category; (b) categories stay open labels, documented as such; (c) add `resource:` as a fifth category and refuse the rest | **settled in round 19: (c)**: `session-file:` and `resource:` are the only two, any other category is refused at `rule add`, and `resource:` writes to `<space>/resource/` |
| N15 | Where does a resource live in the store? | (a) a `resources` table plus `<space>/resource/`, immutable names, a recorded sha256; (b) a `resource:` cell category, versioned like other cells; (c) a plain folder with no store row; (d) no store: the prompt is the rule row's body | **settled in round 18 as (d)**: the body enters through `-F`, a rule row is immutable, and a shared prompt is deferred until two rules need one |
| N16 | What is the surface for the same-session distill? | (a) `--distill RESOURCE` as a one-run target, plus a separate `--run .parent` restart row; (b) the owner's `--resume RESOURCE` with the same one-run meaning; (c) one rule that distills and restarts, two runs and two contracts; (d) three targets: `--run TYPE`, `--resume` in place, `--fork` a copy | **settled in round 18 as (d)**: one rule starts one run; `--resume` is the same-session distill, `--fork` keeps a frozen source, and the fresh continuation stays a separate `--run .parent` row |
| N17 | How does a worker run get a context guard so the distill has room? | (a) a `--guard 70%` flag on the rule; (b) `EMBER_CONTEXT_GUARD` in the engine, default off; (c) no guard, so only wallclock stops and endpoint errors trigger the distill | **settled in round 18 as (a)**: `--guard` is the run's policy and the rule is where policy lives; the worker guards at 70% and the resume rule omits it |
| N18 | Does a `--fork` rule take `--model M` to carry Q17's fallback pair? | (a) yes, fork-only flags, passed to `wisp fork -m`/`-t`; (b) no, the operator forks by hand; (c) a fallback pair per type in `wisp.run.json` | **settled in round 19: (a), as `--model` and `--thinking`**, on every target that forks a dir; `--resume` refuses both because it forks nothing |
| N19 | Does the fault atom carry its reason as the atom's value? | (a) yes: `agent-type:T.failed` gets `value=reason`, so `--event agent-type:T.failed=guard` selects; (b) the reason stays a field and no event can test it; (c) one atom verb per reason | **settled in round 19: (a)**: both `run:<id>.failed` and `agent-type:T.failed` carry `value=reason`, and the cap can count one reason too (`--cap 'agent-type:T.failed=guard<3'`) |
| N20 | Split rules into agents and rules? `ember agent add NAME` carries `--type`, `--require`, `--in`, `--out`, `--guard`, `--wallclock`, `--model`, `--thinking`, `--trace`, and the body via `-F`; a rule keeps `--event`, the target, `--cap`, `--id`; `--run/--resume/--fork agent:NAME`; a rule-level `--in` extends the agent's inputs (exact repeats dropped) and nothing else is overridable. Round 23 removes `--out` from the agent row, so the row carries type, require, in, the two policy flags, model pair, trace, and body | (a) yes, as `rule-language.md` §4.14: agent rows immutable and versioned like cells, run rows pin agent and version, `--resume`/`--fork` ignore the agent's `--type`, bare `--run TYPE` stays as the anonymous form, `.parent` stays for dynamic-type chains; (b) keep the flags on the rule and make `.parent` inherit them; (c) agents without bodies, body stays on resume/fork rules | a — the owner's proposal; the continuation inheritance becomes visible and N1 is subsumed |
| N21 | Disjunction in `--event`? `A or B`, each side a conjunction, one firing from either side | (a) yes, ` or ` at the top level, and `--cap` may take the same form; (b) no, two rules over one agent; (c) a `--event-any` flag | a — "success or failure" and "wallclock or guard" are both one rule's trigger; the fallback today is two rules (review) or the bare `failed` event (rescue) |
| N22 | Is the failure report a first-class input? | (a) no for v0: the persona runs `ember query run:<id>`, which prints the stored report, using the run id the briefing's trigger line names; (b) a `.report` backreference input beside the answer; (c) the engine writes the report into the failed run's work dir | a — zero engine change; revisit if personas prove unreliable |
| N24 | Does `--out` earn its place, or is a run's final message the delivery channel? | (a) drop `--out`: the engine injects the triggering run's answer into the next briefing and keeps `--require` as the typed contract; (b) keep `--out` for files and add the answer beside it; (c) keep `--out` and require a file from every run | **settled in round 23: (a)**, landed in `ember`: the answer rides every firing that names a run, `no_response` replaces the file gate, and a `.` reference in `--in` is refused |
| N23 | The cap spelling: `--cap EXPR<N` glues the threshold to an atom expression, so `agent-type:reviewer.approved<4` reads as a value test on a bool field and `agent-type:worker.failed<4` reads as a numeric test on the reason string. | (a) a required `count(...)` wrapper: `--cap 'count(EXPR)<N'`, and the bare form is refused; (b) keep `EXPR<N` and document that `N` is a count; (c) a separate `--max N` beside `--cap EXPR`; (d) an engine-written `agent-type:T.ran` counter atom | **settled in round 22 as (a)**, and landed in `ember`: a value test goes inside the count (`count(agent-type:T.failed=guard)<3`); (d) stores a derived fact, drifts when a counter write is lost, and counts starts rather than finished runs. |
| N25 | The static human gate: a rule stops and asks a human for typed fields before the work continues. | (a) design A, the owner's `--require-human` on the rule, a `gates` table, `ember gate answer`, atoms `gate:<rule>.FIELD`, gate branches in settle/closure/trees (§4.15 A); (b) design B, the human as a manual agent type: `--run human:LABEL` (under N20, `ember agent add NAME --human`), state `waiting`, `ember answer`, atoms `agent-type:LABEL.FIELD`, guards on `admit`/`reconcile`/`answer_of` (§4.15 B); (c) design C, `--gate NAME` atoms with no waiting state (§4.15 C) | b |
| N26 | A gate nobody answers blocks settlement forever; under N25's design B a waiting manual run is the blocker | (a) `ember answer --dismiss` fails the waiting run with `reason=dismissed`, writing the fault atom a rule may consume; (b) a timeout on the manual run; (c) both | **settled in round 30 as (a)**, landed in `ember/ember`: `apply_answer` runs the dismissal after the manual-and-waiting checks, `finish_failed` writes `run:RID.failed` and `agent-type:LABEL.failed` with `value=dismissed`, and the space settles red instead of hanging; (b) adds a deadline the engine must arm and poll for a row with no process |
| N27 | The daemon's scope: one global hearth or one hearth per space? The per-space shape came from round 12's "v0 is one space end to end", not a decision, and it breaks the Goal's shared cap: `admit` counts `live_runs` on one space's `ember.db`, so two hearths give six concurrent runs | (a) one global hearth: one daemon, one socket at a fixed user path, a space registry, per-space stores, `admit` round-robins registered spaces against a global cap 3, `reconcile` iterates the registry at start, a per-space pause flag, CLI unchanged (`--space` rides the payload); (b) per-space hearths plus a crash-safe global slot ledger (an `flock` per slot, held for the run's life, auto-released on hearth death); (c) per-space hearths and per-space caps, amending the Goal | **settled in round 27 as (a)**, landed in `ember/ember` (see Round 27 and §0.7); the socket, pid, log, and database live at `EMBER_STATE_ROOT` |
| N28 | The store's scope under a global hearth: one SQLite file for all spaces, or one DB per space? One file makes listing spaces and cross-space metrics one query (the UI wish) and makes the global cap exact by construction; per-space files keep the space a self-contained, copyable directory and keep the round-7 cross-space isolation as physics, not query discipline | (a) one DB: a `spaces` registry table (id, path, paused), a space binding on every table and fixed meta key threaded through one query choke point, `atoms.seq` global with per-space ordering kept by filtering, `ember space export` for portability, content (answers, work dirs, traces, session logs) left per space on disk; requires N27 (a) and overrides its per-space-stores clause; (b) one DB per space: the UI walks directories and `ATTACH`es each registered file, no global seq, no one-file listing; (c) one DB per space plus a daemon-written rollup metrics DB | **settled in round 27 as (a)**, landed in `ember/ember`: the binding is the space's directory path on every table and fixed meta key, the registry maps path to id and pause, and `ember space export`/`list` are the portability and listing verbs |
| N29 | Is `hearth` still a required name, and can the daemon verb be `ember space start`? A space is data (a registered directory: rules, atoms, runs, cells, work dirs); the hearth is the only process (one daemon per user at `EMBER_STATE_ROOT`: pump, admit, poll, reconcile, the one-writer law). `ember hearth start` names the process and takes no space; `space init` registers data and `space pause`/`unpause` gates one space's admission | (a) keep `ember hearth start`: the round-2 metaphor still fits — one hearth tending every ember — and the state-root files (`hearth.sock`, `hearth.pid`, `hearth.log`) carry the name; (b) rename to `ember daemon start`: honest and plain, a pure alias with no semantic change; (c) `ember space start`: names the wrong thing, because a space is never started and one daemon serves every space, so no verb can start one space's process; (d) hide the daemon: the CLI auto-starts the hearth on the first mutating verb, which breaks the stateless-client law and adds a spawn-from-CLI mechanism | **settled in round 29 as (b)**, landed in `ember/ember`: the verb is `ember daemon start|stop|status`, the state-root files are `ember.db`, `ember.sock`, `ember.pid`, and `ember.log`, `Hearth` is `Daemon`, and `daemon start` retires a pre-rename daemon that holds the same database instead of letting a second writer open it. (a) keeps two names for one process and names three files after a role; (c) names a start that does not exist |

Dead with the bus in round 9: Q8 (merge window), Q10 (owner inbox and
spawn approval), Q12 (spawn delivery), Q13 (TTL), Q14 (public `--id`),
Q16 (depth cap), Q20 (withdrawn), Q22 (steer expiry), Q23 (prompt key),
Q24 (steer kind), Q28 (join digest), Q32 (template location), Q34
(member-facing send), and the roster and selector questions inside them.
Q30 is superseded: comparisons exist now, on a typed field, and only
aggregate counts over atoms stay a stub. N3 (a fixed cell name per rule)
dies in round 23 with the file cells.

## Settled

| # | Question | Answer |
|---|---|---|
| Q1 | Is the name right? | `ember`, with `hearth`, `stoke`, `--andon` |
| Q2 | What sets the default global concurrency cap? | a constant **3** |
| Q3 | When does `send` wake the recipient? | **superseded in round 8: no member-facing send exists (R8a-R8c).** Round 4 answer kept for the record: **amended this session by the owner.** A **steer** joins a live run at no extra turn and hard-wakes an idle member. A **job** never joins a live run: it is held while the member is live, then a new run starts. Every message ends consumed or expired. The surface for a steer is Q24 |
| Q4 | Is a spawned member woken at once? | **round 8: a spawn is a start, so the run begins at once.** Round 5 answer kept for the record: **no in round 2.** Round 5 amends the surface to `spawn --agent A --job FILE`; Q12 asks whether the job is delivered and wakes the member |
| Q5 | Where does `ember` live? | this repo, `ember/` next to `wisp/` |
| Q6 | Is the warden in scope? | **never** — dropped from the design in round 4; no advisory layer |
| Q9 | Do the twelve spec decisions in round 2 stand? | **superseded** by the round-5 review. `--id`, `await`, `--expect`, `--lease`, `probe`, and `tail` are out; the remaining decisions become Q12-Q21 |
| Q11 | Which wisp idioms beyond the four enter the build, and when? | **round 10 requires nine: W1 (lock only), W2, W4, W5, W7, W10, W11, W12, and W13, with W13 first.** W0 withdrawn, W3 dropped, W6 dead, W8 dropped, W9 rejected, W11 `--from` dropped, and W1's batch, key, and expiry dead. The detailed plan is `wisp-changes.md` |
| R8a | Is cross-agent steering in this version? | **no** (owner, round 8). The only steer is the user's; a user steer starts a new agent that reshapes the space |
| R8b | Is the hard-wake class a separate concept? | **no** (owner, round 8). Every start is a start; a run returns or decomposes |
| R8c | Is delivery acknowledged? | **no** (owner, round 8). The ack is dropped; `rule-language.md` F5 names what replaces it |
| Q25 | Which design: Loom, Foreman, Ledger, or the composition? | **(c) Ledger, by reading**: the owner's examples express the workflow as rule rows, so the Loom template file of (d) is dropped and the Foreman is not wanted. The owner has not confirmed the word in so many words; the round-9 answers (Y5, F1) add rule-row detail and do not contest it |
| Q26 | Rule authorship from a run | **(a) verbs, by reading** |
| Q27 | Typed results | **(a) CLI, by reading**; strengthened: the result row is also the crash witness (F5) |
| Q28 | Join semantics and continuation inputs | **(a) all**, plus an explicit `--in` list, not a concatenated digest |
| Q30 | Do comparisons-only predicates cover every rule? | **superseded in round 9**: comparisons exist, on one typed field per atom (`agent-type:foo.count>3`), because a verdict is now a declared field rather than a fixed verb. Aggregate counts over atoms stay a stub, except in `--cap` |
| Q34 | Member-facing `send`/`dm` in v0 | **(a) engine only**, by reading |
| Q32 | Where does a workflow live? | **superseded in round 9: per space only.** The round-8 answer (a), a rule-row root library, is deferred with F8 |
| Q35 | Is a declared output a checked contract? | **(a) yes** for round 9, and stronger: absent fails `no_output`, unchanged fails `no_change`, each after one re-prompt; every write binds a cell version and a firing pins the version it read (F3, round 9). **Round 23 withdraws the file half**: `--out` is gone, the answer is the delivery channel, and `no_response` replaces the existence check while `no_result` keeps the typed half |
| Q36 | Does the verdict domain live on the type or the rule? | **(b) the rule** (Y5, round 9). The round-8 rec (type) is overturned: `--require FIELD:TYPE` is a rule flag, and the field name is the event verb |
| Q37 | Is the change list advisory or load-bearing? | **(a) advisory**, and since round 10 the source is the run's syscall trace, not a snapshot diff: `strace -ff -y` over a curated set records reads, writes, deletes, and renames with resolved paths, so a write outside the work dir is visible; nono stays a sandbox and is not the recorder (R9e, R10g, §6.3) |
| Q38 | Does a type carry a grant for rules and runs? | **(b) flat authority**, with the creator, the version, and the disabling run recorded on every rule row; grants deferred (Y8, round 9) |
| Q39 | May a conjunction name two multi-run subjects? | **(a) no**, refused at `rule add` with `not implemented in v0` (Y2, round 9) |
| Q40 | Does every space evaluate a root rule library? | **(b) per space only** (F8, round 9) |
| Q41 | What does `--cap` count, and what at the cap? | **an atom count expression**: `--cap 'count(EXPR)<N'` blocks the firing at the threshold, writes `rule:<id>.capped` once, and parks nothing (F1, Y9, round 9; the wrapper is N23, round 22); the counter scope is N2 |
| Q42 | Does a steer reopen a settled space? | **(a) yes**, by derivation: a steer writes an atom, the steward rule fires, so the space is not quiescent |
| N9 | Does the environment switch live on `wisp new` or on `wisp build-system-prompt`? | **(a) `build-system-prompt`** (round 12): `--record`/`--wisp-jsonl` emits the system record, `--include-env` sets `include_env: true`, `new -s` stores a JSON system object as a record and any other bytes as text, and `wisp.run.json` keeps `created` and `project_dir` only. `new --env-in-system-prompt` stays as an alias that sets the marker, so the §4.7 type command keeps working; `sessions_root` derives from `-d`'s parent (round 11) |
| N13 | Does a wallclock stop check the contract before failing? | **no** (owner, round 19): a wallclock stop is a failure, period. `finish_run` tests exit 124 before the contract, writes `reason=wallclock`, and the continuation is a space rule |
| N14 | Is `--out` restricted to the `session-file:` category? | **`session-file:` and `resource:`** (owner, round 19): `rule add` refuses any other category; a `session-file:` output lands in the run's work dir, a `resource:` output lands in `<space>/resource/`, and the cell store versions both. **Void in round 23**: `--out` is withdrawn with both categories |
| N24 | Does `--out` earn its place beside a run's final message? | **no, drop it** (owner, round 23): the engine injects the triggering run's answer into the next briefing, `--out` and its two categories are gone, `no_response` replaces the file gate, and `rule add` refuses a `.` reference in `--in`. Landed in `ember/ember` with 141 checks |
| N18 | Does a `--fork` rule take `--model M` to carry Q17's fallback pair? | **yes, `--model` and `--thinking`** (owner, round 19): both pass to `wisp fork`, so they cover every target that forks a dir; a `--resume` forks nothing and refuses them |
| N19 | Does the fault atom carry its reason as the atom's value? | **yes** (owner, round 19): `run:<id>.failed` and `agent-type:T.failed` carry `value=reason`, so `--event agent-type:T.failed=guard` selects and `--cap 'agent-type:T.failed=guard<3'` counts one reason |
| N23 | The cap spelling: `--cap EXPR<N` or a `count(...)` wrapper? | **`count(EXPR)<N`, required** (owner, round 22): the arithmetic is the count of atoms, while a comparison on a declared field is a value test of one atom. `--cap 'count(agent-type:reviewer.approved=false)<4'` counts the no-go atoms only, and `--event agent-type:reviewer.defects>5` tests an int field. The bare form exits 2, and a stored `{"expr","n"}` row reads unchanged |
| N10 | Is distill-and-continue an engine default or a rule pattern? | **(b) a rule pattern** (owner, round 17): the owner prefers a rule to an engine default. Round 18 amends the shape: the same-session distill is a `--resume` or `--fork` row whose prompt is the rule's body, and the fresh continuation stays a separate `--run .parent` row. The engine-default option (a) is dropped. |
| N11 | Where does the context guard value come from? | **the rule flag `--guard LIMIT`** (round 18), stored on the rule and the run row: the engine passes the string to wisp, which resolves a percent against `wisp.modelcfg` and needs nothing for a token count. `EMBER_CONTEXT_GUARD` is not added |
| N12 | What is a continued run's identity? | **a new run row over the same session dir** (round 18): its parent is the source run, it is started with `wisp run -d <the source dir>` and the rule's prompt, and the tree records the epoch chain. The source row keeps its state, times, and report |
| N15 | Where does a resource live in the store? | **nowhere in v0** (round 18): the prompt is the rule row's body, entered through `-F`; a rule row is immutable, so the body is versioned by the row. A shared resource store is deferred until two rules need one prompt |
| N16 | What is the surface for the same-session distill? | **three targets** (round 18): `--run TYPE` starts a fresh agent, `--run .parent` starts the trigger run's parent's type, `--resume` sends one more prompt into the trigger run's own session, and `--fork` sends it into a copy. One rule starts one run; the fresh continuation is a separate `--run .parent` row |
| N17 | How does a worker run get a context guard so the distill has room? | **`--guard` on the rule** (round 18): the worker guards at 70% of the model's window, the resume rule carries no guard, and a resumed session therefore has headroom for one more turn |
| Q43 | Is the steward one run per space? | **a steer joins, so no slot** (round 10): a second steer appends to the live steward, so no per-type slot is needed and Y7's slots stay deferred for other types |
| Q44 | Unify references on `category:value`, keeping `.` for backreferences and verbs? | **(a) yes** (round 9) |
| R9a | Is the verb set fixed? | **no**: `--require FIELD:TYPE` makes the field a verb, and a verb may carry one comparison test (`<`, `<=`, `>`, `>=`, `=`, `!=`); the fixed verbs stay on `space`, `run:`, `id:`, and the fault verb `failed` |
| R9b | Is an agent type a definition file or a wisp session dir? | **a wisp session dir**, made with `wisp new -d <space>/agent-types --name <type> -s <persona>`; a run is `wisp fork` of that dir, so no type file format exists |
| R9c | Does the engine ever steer a live run? | **no**: `ember steer` writes `space.steer` and a `steer:` cell, and the engine starts a steward run (F4, round 9). Round 10 narrows this rather than reopening it: the engine adds one exception, a steer joining a live run, and a steward run may steer a worker itself; W1's lock returns for that reason |
| R9d | Does a restart inherit the parent's inputs and outputs? | **no**: a `--run .parent` restart re-declares its `--in` (Y6, round 9). Round 23 leaves `--in` only, since `--out` is withdrawn |
| R9e | Is file-change capture load-bearing? | **superseded in round 10**: the recorder is `strace -ff -y` over a curated syscall set around every engine-started run, so a write outside the work dir and a read of `~/.config` are visible; the work dir holds the run's own files, with no declaration (F7, round 10; round 23 drops declared outputs). nono stays a sandbox, not the recorder |
| R10a | May an agent steer a live run? | **yes, the steward may** (owner, round 10): it reads `ember query runs` and runs `wisp steer -d <dir>` with its own words. The engine has one injection and no other: the join of a steer atom into a live run of the rule's target (§4.8) |
| R10b | Does a second steer start a second steward? | **no**: a steer joins, so the firing's inputs append to the live steward and the atom is consumed; a freed lock escalates to a start, so a wrong guess costs one run and never a message. Q43 settles, no slot |
| R10c | What does `.done` on a type mean? | **the closure of a decomposed job**: every run carries an inferred parent (the lowest common ancestor of the trigger runs), `agent-type:T.done` fires once per root when the whole tree is green, a green repair stops a failure poisoning its tree, and a run started from a closure atom is a new root so closure cannot deadlock (§4.11) |
| R10d | How good is the failure message? | **named and reproducible**: field, type, run, rule, version, trigger atom with its seq and source run, start and end times, exit, re-prompt count and time, the result rows set, the work dir, a 200-character excerpt of the last model words, and the fix command (§4.3.1) |
| R10e | Can the fork avoid rewriting the log? | **yes**: the `<environment>` block becomes a view rendered at request time from `wisp.run.json` and `-d` (W13); `fork` copies `wisp.jsonl` and `wisp.run.json`, sets `created`, and rewrites no record |
| R10f | How does a body enter an `ember` verb? | **`-F FILE` or `-F -` only**; no verb reads bare stdin and none takes a body positionally; argv carries scalars and labels; a missing `-F` on a pipe is a `usage` error that names `-F -` (§4.12) |
| R10g | Is a snapshot diff enough to record file changes? | **no**: `strace -ff -y` with a curated syscall set wraps every engine-started run, records reads, writes, deletes, and renames with resolved paths, and costs 0.32 s and 0.66 MB per `python3` tool call; the raw trace is deleted after the parse unless the run failed; a rule may pass `--trace none` for a type that must not pay it (§6.3) |
| N25 | The static human gate: a rule stops and asks a human for typed fields before the work continues. | **(b) the manual agent type** (owner, round 25): `--run human:LABEL` (under N20, `ember agent add NAME --human`), run row `mode manual` in state `waiting`, `ember answer` completes it through the unmodified `finish_success`, atoms are `agent-type:LABEL.FIELD`, guards on `admit`, `reconcile`, and `answer_of`, and a dirless `waiting` row is excluded from `reconcile` (§4.15 B); a human is a type of agent |
| N27 | The daemon's scope: one global hearth or one hearth per space? | **(a) one global hearth** (owner, round 27), landed in `ember/ember`: one daemon per user at `EMBER_STATE_ROOT` (default `~/.local/state/ember`, 0700), the space rides the request payload, the cap counts live runs across every space with round-robin admission, `reconcile_all` walks the registry at start, and `ember space pause`/`unpause` holds one space's admission while its rules still fire |
| N28 | The store's scope under a global hearth: one SQLite file for all spaces, or one DB per space? | **(a) one DB** (owner, round 27), landed in `ember/ember`: a `spaces` registry table (id, path, paused, created), the directory path as the space binding on every table and fixed meta key, global `atoms.seq` and globally unique run ids with per-space queries filtering by the binding, `ember space export [-o FILE]` for portability, `ember space list`, and content left per space on disk; per-space stores from rounds 12-26 are not migrated |
| N26 | A gate nobody answers blocks settlement forever; under N25's design B a waiting manual run is the blocker | **(a) `ember answer RID --dismiss`** (owner, round 30): the flag takes no `--field` and no `-F`, `apply_answer` calls `finish_failed` with `reason=dismissed`, the fault atoms carry `value=dismissed` so a rule selects the reason, the root's tree goes red, and the space settles; a dismissal of a done gate, a model run, or one carrying fields is refused with exit 2 |
| N29 | Is `hearth` still a required name, and can the daemon verb be `ember space start`? | **(b) rename to `ember daemon start`** (owner, round 29), landed in `ember/ember`: `daemon start|stop|status` with the hidden `_serve` spawn, `Hearth` renamed to `Daemon`, and the state-root files named `ember.db`, `ember.sock`, `ember.pid`, `ember.log` — one stem for every file the program writes, while `daemon` names the process and only the process. `daemon start` retires a pre-rename daemon (`hearth.sock`) because the old daemon writes the same database: two writers on one file is the law this daemon exists to keep. No alias: `ember hearth` exits 2 |
