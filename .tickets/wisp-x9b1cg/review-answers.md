# Round 5 review answers

Status: answers to the owner's review of `api-spec.md` round 2 and the
wisp changes list. The decisions here are applied to `api-spec.md`
(round 3), `wisp-changes.md`, and `ticket.md`. No `wisp` code changes.

**Round 4 amendment.** The owner withdrew W0 `wisp send`. The transport
keeps `wisp run`, `wisp continue`, and `wisp steer` separate; a delivery
is a JSONL batch to `wisp steer --batch`, and a hard wake adds `wisp
run` with a constant trigger. Sections 1, 17, 21, 22, and the Q20 row
below carry the amendment.

## 1. Delivery proof: the typed id in `wisp.jsonl`

**Quote:** "Delivery is proven by the typed id in `wisp.jsonl` — How
does that happen? I said `ember` cannot leak into `wisp`."

The round-2 plan leaked: the steer line carried `ember_id`, and `wisp`
copied that name onto the steered record. That put an `ember` word
inside `wisp`.

The round-3 plan uses a generic **steer key**:

1. The hearth calls `wisp steer --batch` with a JSONL line that carries
   an opaque `key`: `{"content":"...","key":"12a1"}`.
2. `wisp` appends the line to `<session>/wisp.steer.inbox` under the
   steer lock, drains it as a steered user record, and writes
   `wisp_steer_key: "12a1"` on that record in `wisp.jsonl`.
3. The hearth reads the key from the committed record. The hearth
   writes `msg.consumed 12a1`. The exit code of any process never
   acknowledges a message.
4. A key already present in the session is skipped. A run killed before
   the commit leaves no key, so the hearth redelivers.

`wisp` never learns the word `ember`. `wisp` learns one generic idea: a
message may carry a caller key; the key is persisted and deduplicated.
The key on the digest block is absent; only body blocks carry a key, so
the digest cannot acknowledge a body.

`wisp status -d DIR --json` exposes committed keys, so the hearth does
not parse `wisp.jsonl` directly. The JSONL remains the truth; the status
view is a supported read.

## 2. Body input: no argv strings

**Quote:** `ember dm w2 "$(cat plan.md)"`

The round-2 plan allowed argv under 4 KB, bare stdin, and `-F`.
Round 3 allows one form:

```
ember dm w2 -F plan.md
ember dm w2 -F -          # stdin
```

`-F` is required. `-` names stdin. Nothing is lost: a one-line message
is a one-line file, or `printf 'one line\n' | ember dm w2 -F -`. The
argv size check and exit 6 are gone. A missing `-F` is a usage error,
exit 2.

## 3. `--expect reply`

**Quote:** "What is `--expect reply`?"

It was a request marker. It told the digest to list an open request and
it let `ember await` block for a reply. Round 3 removes it. The system is
fully asynchronous: a member that needs a reply stops; the reply wakes
it. A reply is a normal message with `--re MSGID`. No request table, no
waiter, no timeout.

## 4. `ember probe`

**Quote:** "What is `ember probe` and what is `prompt 812 tok completion
96 tok`?"

`ember probe` was a paid smoke test for a template and a model pair. It
ran one real turn with a fixed prompt. The numbers were the provider's
token usage: `prompt 812 tok` was the request, `completion 96 tok` was
the response.

Round 3 drops `ember probe`. The router is an external command, so test
the router directly: `llm_route reviewer`. A spawn can print the resolved
route with `--dry-run` without a model call; that is a proposed
convenience, not a separate verb.

## 5. `--job` is a file

**Quote:** "as a file please, don't take possibly large prompts through
positional arguments."

Round 3 makes every job a file:

```
ember join lab --name alice --agent lead --job alice.job
ember spawn --agent reviewer --job audit.job --name aud
```

`--job -` reads stdin. No positional job text.

## 6. `--lease DUR`

**Quote:** "I don't like this, drop it."

Dropped. A member ends by `left`. The owner may `left` another member.
A member with no live run is idle, not dead. No lease field, no lease
expiry, no eviction reason.

## 7. Body sources: argv under 4 KB

**Quote:** "Again, no, just the file input."

Dropped. See item 2. Only `-F FILE` and `-F -`.

## 8. `ember await`

**Quote:** "I want the system to be fully async. If an agent needs
something, it can stop. A message will wake it up."

Dropped. `ember await`, the `msg.await` op, the waiter table, and exit 9
are gone. A reply is a message with `--re`. The requester's run can end;
the reply starts a new run.

## 9. `--ttl S`

**Quote:** "What is the use case for this? I'm trying to keep the API
minimal, I need to understand why did you want to add this."

The use case is stale mail. A message to an idle member may wake hours
later. Without a bound, the queue grows and a broadcast can spend tokens
on work nobody wants anymore. TTL gives an expiry row and no run.

Round 3 keeps the mechanism but removes the per-send flag. One root
policy `message_ttl_s`, default **3600**, bounds every delivery. A sender
does not choose a TTL. If a per-message override is needed later, it is
one flag; the default does not need it. This is Q13.

## 10. `--id SENDID`

**Quote:** "Again, tell me the use case."

The use case is a retry after a dropped socket. Without an id, a retry
delivers the same body twice. Round 3 removes the public flag. The CLI
generates an internal request id and retries a dropped connection once;
the hearth dedupes on `(actor, request_id)`. A user-level retry is a new
send, because the user made a new decision. This is Q14.

## 11. `--corr C`

**Quote:** "what is this?"

It was a correlation id for request/reply and for `log` filters. Round 3
removes the public flag. `--re MSGID` sets the thread. `ember log --re
MSGID` filters by it. The database column `corr` stays internal.

## 12. `ember tail`

**Quote:** "who uses when?"

An operator watching events live in a terminal. The read-only SSE UI
covers the browser. Round 3 drops `tail` from the CLI. `ember log` reads
the past; the UI streams the present. If a terminal follow is needed,
one `log --follow` flag is cheaper than a second verb. This is Q15.

## 13. Spawn: T, J, R, E

**Quote:** "What is the difference between T, J, R and E? I want to
define an agent and hand it a prompt, that's it."

Round 2 had four concepts: template (persona), job (why), role
(selector), expects (acceptance). Round 3 collapses them:

```
ember spawn --agent A --job FILE [--name N]
```

- `--agent A` names one agent definition.
- `--job FILE` is the prompt and the task.
- `--name N` is optional; the name is how peers address the member.

The agent definition carries the persona, the route type, the role, the
default wall clock, and the expectations. The definition is one
human-editable Markdown file with frontmatter.

Round 3 also proposes that `spawn` delivers the job as the first message
and starts the member. That is the literal reading of "hand it a
prompt." It amends Q4 (a spawn would no longer be free). This is Q12.

## 14. `depth` and recursive agents

**Quote:** "Is this blocking recursive agent definitions? Where an agent
would spawn a reviewer that spawns an implementer that spawns a
reviewer..."

No. `depth` counts generations, not types. An agent may spawn any type.
`max_depth` is a fork-bomb bound, not a type ban. With `max_depth 2`, a
chain of three spawns is denied; a reviewer may still spawn an
implementer, and that implementer may spawn a reviewer if the policy
allows the depth.

Round 3 keeps `max_children` and `max_members` and asks whether
`max_depth` earns its place as a third knob. This is Q16. The member
record keeps `depth` for audit either way.

## 15. `ember probe` again

Dropped. See item 4. `llm_route <type>` is the test surface.

## 16. `model.default` and `model.fallback`

**Quote:** "I don't want global defaults. An agent definition will name
a type (e.g. thinker, worker, reviewer), and there'll be a router for
this, an external command. Think `llm_route thinker`."

Round 3 removes both policy keys. An agent definition names a `type`.
The hearth calls an external router:

```
llm_route reviewer
```

Proposed contract: stdout is one JSON line:

```
{"model": "...", "thinking": "...",
 "fallback": {"model": "...", "thinking": "..."}}
```

A nonzero exit denies the spawn or the run, with the router's stderr as
the reason. The policy key `router.command` defaults to `llm_route`. The
router owns the model mapping, the thinking level, and the fallback. The
hearth records `route.resolved` for audit. This is Q17.

## 17. Wall clock

**Quote:** "OK with a default for now, but must be settable per run."

Round 3 keeps **600 s** as the default and adds `--wallclock S` to
`send`, `dm`, and `spawn`. The message carries the value. A run uses the
minimum wall clock among its pending messages. `wisp run --wallclock S`
enforces the limit; the hearth does not arm a separate timer. This is
Q18.

**The wake line.** Round 2's `--prompt-file` carried one constant line
that the hearth fed to a closed-tail run:

```
Stoked: read the ember digest above and answer what is addressed to you.
```

The line existed because `wisp run` needs a prompt and the bodies ride
the inbox. With W0 withdrawn, ember passes the constant trigger itself
on `wisp run` stdin, and the bodies ride the inbox. No `--prompt-file`,
no `--prompt`, and no `wisp send` flag exist.

## 18. Guard 75

**Quote:** "Distill immediately."

Round 3 removes the one-time guard raise. The first guard 75 distills.
The recipe follows `wispy`:

1. The stopped session runs one distill turn with no context guard.
   `wisp response` returns the summary.
2. The hearth creates a new session with the same agent persona and a
   new epoch.
3. The new session starts with the member's job and the summary.
4. The hearth writes `member.distilled`, updates `session_dir`, and
   requeues pending deliveries.

The member id and the job survive. There is no `wisp compact` command.
This is Q19.

## 19. One live run per member

**Quote:** "What does this mean, that e.g. 2 agents of the same type
cannot run concurrently? I'd disagree if that was the case."

It means one live run per member **session directory**. Two members of
the same agent type have different member ids and different session
directories; they run concurrently, subject only to the global cap of 3.
The rule protects one `wisp.jsonl` from two writers. It never groups
members by type.

## 20. Body digest pointer

**Quote:** "Body digest pointer, what where?"

The digest is a steer record with the roster, message ids, counts, and a
120-character excerpt per message. The digest never carries a body.

The body is a second steer record. At most 2 KB, that record carries the
body text. Over 2 KB, that record carries a pointer:

```
[ember:12b3] owner -> w2 handoff 14 KB sha256 ab12...
read it with: ember show 12b3
```

The body lives in the hearth's SQLite `bodies` table, keyed by sha256.
The reader pays one tool call only if the body matters. The pointer is
in the steer inbox and then in `wisp.jsonl`; the body is in the database.

## 21. `wisp send`

**Quote:** "I want a `wisp` change where the prompt input will go into a
file in the session directory... Instead of `wisp run` we will have
`wisp send`... A running `wisp send` monitors the input file and includes
it as steering. This file is human editable, i.e. not JSONL."

**Withdrawn in round 4.** W0 merged `wisp run`, `wisp continue`, and
`wisp steer` into one command over one prompt file. The owner retracted
the merge:

- The prompt file was input, not a log; `wisp.jsonl` is the durable
  record, and a steered record commits at the drain.
- The `<!-- wisp:message -->` header existed only to pack several
  messages into one file; without the file, the JSONL `key` field
  carries the ack.
- `-F FILE` had no job: `wisp run` and `wisp steer` already read stdin.
- The commands have different intents, and ember knows the intent at the
  call site.

The replacement is W1 `wisp steer --batch` plus the existing `wisp run`
and `wisp continue`. See `wisp-changes.md`, round 4. Q20 is closed by
this withdrawal.

## 22. Wisp tiers

**Quote:** the per-item list after "As per the unanswered wisp update
proposals."

| Item | Decision |
|---|---|
| Tier 0, 2 run lock | accepted |
| Tier 0, 3 resume | dropped; `wisp continue` covers it |
| Tier 0, 4 exit table | accepted |
| Tier 1, 5 status `--json` | accepted; it also carries committed steer keys |
| Tier 1, 6 ack index | deferred; the use case is a long-lived session with many turns, and short-lived sessions do not pay the scan |
| Tier 1, 7 model set | replaced by `wisp fork` |
| Tier 1, 8 compact | dropped; use the `wispy` distill recipe |
| Tier 1, 9 ephemeral | rejected; messages stay immutable for prefix cache |
| Tier 1, 10 stream | `--no-stream` accepted; stdout redirect stays |
| Tier 1, 11 `-d` / `--from` | `-d` accepted; `--from` explained and proposed dropped |
| Tier 1, 12 wallclock / prompt file | `--wallclock` accepted on `run`/`continue`; the prompt file is withdrawn with W0 |

## 23. `wisp fork`

**Quote:** "I'd rather have `wisp fork` to create a session copy. This
command can allow changing model and thinking."

Proposed:

```
wisp fork -d SRC [-o DST] [--name N] [-m M] [-t T]
```

`wisp fork` copies `wisp.jsonl` and `wisp.run.json`,
the prompt cursor into a new session directory. It rewrites
`wisp.run.json` and the `<environment>` block's model and thinking lines.
It leaves the source untouched. Ember uses it for a fallback retry. This
is Q21.

## 24. Compaction and `wispy`

**Quote:** "compaction is a misnomer in `wisp`. You run a new `wisp`
session with a distill/compact prompt, take `wisp response` and put it in
a new session. Check what `wispy` does."

`wispy` runs the distill turn in the **same** stopped session, with no
context guard. It saves the assistant response as `STATE.md`. The next
work session is a new session, and the state block is part of its first
prompt. `wispy` does not compact the log and does not add a `wisp
compact` command.

Round 3 adopts that recipe for ember. `wisp compact` is dropped. This is
Q19.

## Questions for the owner

| # | Question | Options | Rec |
|---|---|---|---|
| Q12 | Does `spawn` deliver the job and wake the member? | (a) yes, one command; (b) no, keep the separate `dm`; (c) `--start` opt-in | a |
| Q13 | Is TTL one root policy or a per-send flag? | (a) root policy `message_ttl_s`; (b) `--ttl S` per send; (c) both | a |
| Q14 | Is public `--id` needed? | (a) no, internal retry id; (b) keep `--id`; (c) no dedupe | a |
| Q15 | Is `ember tail` needed? | (a) drop; UI streams; (b) `log --follow`; (c) keep `tail` | a |
| Q16 | Is `max_depth` needed beside `max_children` and `max_members`? | (a) keep as a third cap; (b) drop; (c) keep only for spawned members | b |
| Q17 | What is the router contract and fallback shape? | (a) one JSON line with `model`, `thinking`, `fallback`; (b) two commands; (c) plain text lines | a |
| Q18 | Which wall clock wins when a run has several pending messages? | (a) minimum; (b) first; (c) member/agent default only | a |
| Q19 | Distill in the same session then start a new session? | (a) yes, the `wispy` recipe; (b) distill in a new session seeded with `render-past`; (c) other | a |
| Q20 | `wisp send` details: delimiter, trigger prompt, `continue` | **withdrawn with W0;** no block file, no header; `continue` stays | — |
| Q21 | `wisp fork` destination and copy set | (a) new dir under the sessions root, copy log/run/prompt; (b) `-o` required; (c) copy only the last N records | a |
