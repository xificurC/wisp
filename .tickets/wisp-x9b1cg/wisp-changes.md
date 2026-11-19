# wisp changes for ember

Status: plan, round 10. **Do not change `wisp` yet.** Round 10 keeps the
rule-engine pivot's set, adds one change (W13, the request-time
`<environment>`), and brings one back (W1, the steer lock only). The
rejected and superseded material is a log at the end of this file; the
required list is clean.

The rule for a `wisp` change: `wisp` already owns the file, the format,
or the process, and the change removes a duplicate implementation or
closes a race. `wisp` exposes facts and mechanisms. Policy stays in
`ember`.

## Required changes

**Implemented in round 12.** The nine changes are in `wisp/wisp`, with
tests in `tests/test_wisp_changes.sh`; ember is the first consumer.
`sessions_root` follows round 11's derivation from `-d`'s parent.

| # | Change | Why ember needs it |
|---|---|---|
| W13 | render `<environment>` at request time | the block is a view, not a record, so a fork needs no rewriting and a model switch stops lying |
| W11 | `wisp new -d DIR` | an agent type is a session dir inside the space: `wisp new -d <space>/agent-types --name verifier` fails today (`wisp/wisp` 1792: `new` is not in `SESSION_DIR_COMMANDS`, and the flag table has no `-d` for it) |
| W7 | `wisp fork` | a run is a fork of the type dir; with W13 a fork is a plain copy |
| W2 | run lock | the liveness record: the startup scan, the join-versus-start test, and one live run per session dir |
| W4 | exit table plus machine line | 75 and 78 are engine signals, and 76 is the lock |
| W5 | `status --json` | the engine reads the tail, the lock holder, and the model without parsing `wisp.jsonl` |
| W1 | steer lock (`flock` only) | two processes append to one inbox: the engine's joined steer and a steward's own `wisp steer`. The rename race is reproduced |
| W10 | `--no-stream` | the hearth spawns every run; no terminal is attached |
| W12 | `--wallclock` | a stuck run must not hold a slot |

Nine items. None exists yet. W1 and W13 are small; W7 depends on W13;
W11 depends on nothing.

### W13. `wisp new` stops baking `<environment>`

Today `new_session` builds the block with an absolute `SESSION DIR`, the
creation time, the model, and the thinking, and prepends it to the
persona before writing the system record (`wisp/wisp` 231–243, 426–440).
The block is then the first thing in `wisp.jsonl` forever.

Three consequences bite:

- A copy of the log carries the source's paths, so a fork must rewrite
  the record. Round 9 proposed exactly that; the owner rejected editing
  records as hacky, correctly: it is a rewrite of the log the whole tool
  treats as append-only truth.
- `MODEL` and `THINKING` are baked, so rewriting `wisp.run.json` before
  `wisp continue` switches the model while the prompt still names the
  old one (verified round 1).
- The creation time exists nowhere but in that prose. Records carry no
  timestamp field, so no second source can render it.

The change:

- `wisp new` writes the persona alone. `wisp.run.json` gains `created`,
  `sessions_root`, `project_dir`, and `env_in_system_prompt`.
- Every request builder composes `<environment>` from `wisp.run.json`
  and the `-d` path, then the stored persona. The three builders are
  `body_of_chat`, `body_of_responses`, and `body_of_anthropic`
  (`wisp/wisp` 3676–3860).
- A stored system record that already begins with `<environment>` has
  the element stripped and re-rendered. This is the only branch that
  reads the old format, and it is what keeps existing sessions and old
  forks correct.
- `wisp render-past` renders the same block, so the display matches what
  the model saw.
- `--env-in-system-prompt` keeps its meaning and moves its effect from
  `new` time to request time.

The block is byte-identical across a session's runs: the directory and
`created` are fixed, and the model pair changes only when the run setup
changes. The prefix cache holds.

### W11. `wisp new -d DIR`, where DIR is the parent directory

```
wisp new -d <space>/agent-types --name verifier -m MODEL -t THINKING \
     --env-in-system-prompt -s < <(wisp skill read falsifier)
```

creates `<space>/agent-types/verifier` and prints that path.

- `-d DIR` is the parent; `--name` is the leaf. Without `--name`, the
  leaf is a rand8, as today.
- `DIR` is created with its parents when it does not exist.
- `-d` on `new` names a destination root, not an existing session, so
  it must not share `resolve_sessiondir`'s validator; that function
  fails on a missing directory and binds `WISP_SESSION_DIR`.
- The sessions root is still registered for `ls` and `grep`, so a type
  dir inside a space is still discoverable.
- `--parent` is unchanged.

The owner's type command passes both flags, so the leaf semantics is the
one that makes the command work.

### W7. `wisp fork`

```
wisp fork -d SRC [-o DST] [-m MODEL] [-t THINKING]
```

- Copy `wisp.jsonl` and `wisp.run.json` to the destination. With W13 no
  record is rewritten; `created` is set to now and the rest of the setup
  is copied or overridden by `-m`/`-t`.
- Default destination: `<src parent>/<src name>-fork-N`, first free N.
- The destination is created atomically: build in a sibling temp dir,
  then rename.
- The fork takes the source's run lock non-blocking for the copy and
  exits 76 if a run holds it, so a live source cannot be copied
  mid-commit. It releases the lock after the copy.
- The source's records, setup, stream, and usage are untouched.
- `wisp.jsonl` is copied record for record, so the fork inherits the
  source's context. Ember's type dirs are created and never run, so a
  fork of one carries the persona alone. A user who runs a type dir
  before forking inherits that history; that is the user's choice, not a
  bug.

### W2. Run lock

`flock` on `<session>/wisp.run.lock` for the life of `wisp run` and
`wisp continue`. The file holds the pid and the process start time. A
second command that needs the lock exits **76** with the holder's pid
and start time, on stderr and in the machine line.

- `wisp steer` never takes this lock: it appends to the inbox, which is
  safe under W1's steer lock.
- The lock is the liveness record. A process that dies releases it, so
  the hearth's startup scan can tell a live run from a dead one without
  reading `/proc`, and the join-versus-start test is a non-blocking try.
- The file is never deleted. Its content is a hint; the held flock is
  the fact.

### W4. Exit table and machine line

```
0    success
1    generic failure
2    usage
75   context guard
76   run lock busy
77   HTTP error (machine line carries status and retry_after)
78   nothing to run or continue
79   degenerate stream
124  wall clock
128+n killed by signal n
```

Every nonzero exit writes one machine line on stderr, and the same line
goes to `wisp.log`:

```
wisp: error kind=<kind> status=<http-status> retry_after=<seconds> <message>
```

The fields after `kind` are optional. Kinds: `http`, `busy`, `guard`,
`nothing`, `degenerate`, `wallclock`, `usage`, `internal`. `wisp
continue` on a closed tail exits **78**, not 1. `wisp run` with empty
stdin exits **2**.

### W5. `wisp status --json`

```
wisp status -d DIR [--json]
```

```
live            bool
pid             int | null
start           ISO-8601 | null
lock_holder     {pid, start} | null
tail            "open" | "closed" | "empty"
commit_seq      int
steer_inbox     int
created         ISO-8601
model           string
thinking        string | null
last_error      {kind, status, retry_after, message, ts} | null
usage           {prompt_tokens, completion_tokens, total_tokens}
```

`committed_keys` is out: no ack exists in ember. `created` is new in
round 10 and comes from `wisp.run.json`.

### W1. Steer lock, lock only

`wisp steer` and `steer_intake` take one `flock` on
`<session>/wisp.steer.lock`: the writer around open, append, and close;
the intake around rename, read, and remove. Without it an append that
lands after the intake's rename goes into the consumed file and is lost
(reproduced in round 2 with no model; closed by exactly this lock in
round 3, 50 runs, 0 losses).

Nothing else from round 4 is needed:

- No `--batch`: the engine writes one line per join, and the steward
  writes prose.
- No `--key`: no ack exists.
- No `--ttl-s`: no expiry exists.
- The verb keeps its current prose contract for a human and for the
  steward. `wisp steer` still reads the whole stdin as one message.

The lock is required because two processes now reach one inbox: the
engine's joined steer, and the steward run's own `wisp steer`. The
engine alone would be a single writer; a model with bash is not.

### W10. `--no-stream`

Add `--no-stream` to `wisp run` and `wisp continue`. The hearth passes
it; a human redirects stdout or watches the stream. No `--stream FILE`
in v0.

### W12. `--wallclock`

Add `--wallclock S` to `wisp run` and `wisp continue`. Default 600 s.
SIGTERM at the limit, 5 s grace, then SIGKILL. Exit 124, or 128+15 for
the SIGTERM path.

## Build order for wisp

1. **W13** request-time `<environment>`. Everything else that copies a
   session depends on it.
2. **W11** `wisp new -d DIR`, parent semantics. A type cannot be made
   without it.
3. **W7** `wisp fork`, a plain copy under W13. A run cannot start
   without it.
4. **W2** run lock and **W4** exit table. The liveness record and the
   signals.
5. **W1** steer lock. Small, and independent of the rest.
6. **W5** `wisp status --json`.
7. **W10** `--no-stream` and **W12** `--wallclock`.

W13 first is the one ordering change round 10 makes. Round 9 put W11 and
W7 first and let `fork` rewrite the record; that rewrite is gone, so the
render change comes before the copy.

## What is not a wisp change

The owner's two remaining requests land in ember, and this file records
why.

- **`-F` on every `ember` verb.** ember's CLI is ember's. `wisp run`,
  `wisp continue`, and `wisp steer` read stdin, and they keep that
  contract: `wisp steer` has a documented human form and `wispy` pipes a
  ticket into it. The steward wraps `wisp steer` in a shell redirect, so
  it never sees the flag. The contract is in `rule-language.md` §4.12.
- **`strace` around a run.** The hearth spawns `wisp run`, so ember
  wraps its own child:

  ```
  strace -ff -y -s 0 -e trace=<curated> -o <space>/logs/<rid>/trace \
    wisp run -d <space>/runs/<rid> --no-stream
  ```

  No `wisp` code is involved, the exit code passes through, and the
  trace file per pid is the attribution. The measurements are in
  `rule-language.md` §6.3.

## Log of rejected, dropped, and superseded changes

Newest first. Each entry says what it was, why it died, and what
replaced it.

### W1's batch, key, and expiry (rounds 4–10, dead)

Round 4 asked for `wisp steer --batch` with JSONL framing, `--key` for
the ack and the retry dedupe, and `--ttl-s` for expiry. Round 8 killed
the digest that framed the batch. Round 9 killed the ack when the engine
stopped steering live runs. Round 10 has one engine writer and one
steward writer, each sending prose or one line, so none of the three has
a caller.

The tested reason the flag existed: three JSONL lines piped to `wisp
steer` without `--batch` land as one steered record holding the raw
JSONL text, and the intake drops `key` (round 6, fake endpoint). That
fact stands; nothing needs it any more.

### The round-9 fork rewrite (dead)

Round 9 required `wisp fork` to rewrite the `<environment>` block inside
the copied `wisp.jsonl`: `SESSION DIR`, `SESSION CREATION TIME`,
`MODEL`, `THINKING`, and `SESSIONS ROOT`. The owner called it hacky and
asked for a `wisp`-level simplification that does not push a JSONL
rewrite into `wisp`. W13 removes the cause instead: the block is never a
record, so a fork copies records unchanged.

### W7 `wisp model set` (dead)

The round-4 form of W7 was a verb that rewrote `wisp.run.json` and the
baked model pair. `wisp fork` replaced it in round 4, and W13 makes the
baked half disappear. A model switch is now: edit `wisp.run.json`, then
run; the rendered block follows.

### W11 `--from TEMPLATE` (dead)

`wisp new --from TEMPLATE` would copy a never-run session dir. `wisp new
-s PERSONA` plus `wisp fork` already covers both halves: a persona at
creation, a copy of a whole session at fork. A second template format
duplicates `wisp.jsonl`.

### W0 `wisp send` and the prompt file (withdrawn, round 4)

W0 merged `wisp run`, `wisp continue`, and `wisp steer` into one command
over one human-editable prompt file. The owner withdrew it:

1. **The file is input, not a log.** `wisp.jsonl` is the durable record;
   a prompt file was a second queue.
2. **The header was unnecessary.** `<!-- wisp:message -->` existed only
   to pack several messages into one Markdown file.
3. **`-F FILE` had no job.** The prompt file was the command's target,
   not its source.
4. **The commands have different intents.** `run` sends input and
   expects output; `continue` sends no input; `steer` sends input and
   expects no output. Ember knows the intent at the call site.

No `wisp send`, no `wisp.prompt.md`, no watcher, no trigger file, no
header.

### W3 `wisp resume` (dropped)

`wisp continue` already resumes an open segment. A closed tail exits 78,
which tells ember to call `wisp run`. No separate verb.

### W6 ack index (dead)

The ack index existed to make a per-message ack cheap on a growing
`wisp.jsonl`. Round 8 dropped the ack, so there is nothing to index.

### W8 `wisp compact` (dropped)

`wisp` has no compaction. The recipe is `wispy`'s: one distill turn with
no guard, read the summary, create a new session with the same persona,
start it with the job and the summary.

### W9 ephemeral steer (rejected)

A message that disappears breaks the prefix cache and the audit. Messages
stay immutable.

### The round-4 transport table (superseded)

Kept because it names the failures the pivot removed. Each row assumed
delivery into a member; the rule engine has no members.

| Situation | Command | Why it died |
|---|---|---|
| join, no wake | `wisp new` | membership is out; a type is a dir |
| new job, member idle | `wisp run` | a job is a rule firing, not a message |
| new job, member live | hold, then `wisp run` | a start is the only job transport |
| digest plus bodies, member idle | `wisp steer --batch`, then `wisp run` | the digest and the batch are gone |
| a steer, member live | `wisp steer --batch` | survives as the steer join, without `--batch` or a key |
| resume a killed segment | `wisp continue` | survives, as a wisp fact |
| fallback model | `wisp fork`, then `wisp run` | survives, deferred to v3 |
| ack | `status --json` `committed_keys` | no ack |
| liveness | `status --json` `live` / `lock_holder` | survives as W2 and W5 |

### The round-8 build order (superseded)

v0 store, hearth, atoms, rules, cells, typed results, start plus
admission, cap 3, `ember why`, `trigger show`, `query` → v1 the root
rule layer plus grants, caps, and parks → v2 the steward and the
conditional steer → v3 crash reconciliation, fork, distill → v4 UI
(task graph). Round 9 dropped the root layer and the conditional steer;
round 10 adds the tree, the failure report, and the tracer to v0 and
moves the steward, the steer join, and `ember steer` to v2.

### The round-4 tier table and build order (superseded)

The round-4 set was W2, W4, W5, W7, W10, W11, W12 in that order, with W1
included and W0/W3/W6/W8/W9 out. Round 9 removed W1; round 10 puts the
lock back and prepends W13. The round-4 order put the run lock first
because two runs in one directory was the live bug; that bug is a fork
now.

### The dead open details (Q20, Q22, Q23)

| # | Detail | Fate |
|---|---|---|
| Q20 | prompt-block delimiter | withdrawn with W0: no block file, no header |
| Q22 | an expiry on a steer line | dead: no TTL exists, and a joined steer is at-least-once |
| Q23 | `wisp run --key K` | dead: no ack exists |

## Open details

| # | Detail | Options | Rec |
|---|---|---|---|
| Q21 | Fork destination and copy set | (a) default `<src>-fork-N`, `-o` overrides, copy the log and the setup; (b) `-o` required; (c) copy only the last N records | a |
| N7 | Does `wisp new -d DIR` create missing parents? | (a) yes; (b) fail unless DIR exists | a: `<space>/agent-types` may not exist yet |
| N8 | Does `--env-in-system-prompt` default on for a session made with `-s`? | (a) keep it opt-in, as today; (b) default on | a: changing the default changes every prompt, and the flag already works |
