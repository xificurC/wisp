# wispy

`wispy` drives one ticket through short `wisp` sessions. It does the
bookkeeping: the phases, the state handoff, the responses, and the
commit.

## Why it exists

An earlier tool in this line ran a fixed lifecycle. The tool owned a
state machine with one command per step: frame, plan, execute, settle,
close. The operator could not change the depth of a session. A shallow
task paid for every phase anyway.

`wispy` keeps the bookkeeping and drops the lifecycle. The operator
chooses the depth with the skills:

| Task | Command |
|---|---|
| Frame a new ticket | `wispy run --skills frame` |
| Do a design round | `wispy run --skills design` |
| Close the ticket | `wispy run --skills close-ticket` |

The session is composable. The ticket is the constant.

## The command surface

```text
wispy run      [--skills LIST] [flags]          < request
wispy continue [--skills LIST] [flags]         [< request]
wispy steer                                    < message
wispy commit   [--skills LIST] [--close] [flags]  [< brief]
wispy response
```

`WISPY_TICKET` is the only binding. It holds a path or an id. An empty,
unset, or unresolved value exits 2 before any model call.

`wispy commit --close` writes `status: 'closed'` into the ticket before
the commit prompt is built, so the committed record carries the final
status. Without `--close`, the subject carries the status that the ticket
holds when the command starts.

The commit session also owns the ticket name. The name written when the
ticket opened often states the request, not the work:
`can wisp render-live stream tool calls?`. The session rewrites the
`name:` line as a definition of the work done,
`wisp render-live: stream tool calls and their results`, and builds the
subject `<status>(<id>): <name>` from that name. `wispy` writes one
ticket field, the status; the session writes the name.

The subject is never frozen into the prompt. The prompt header carries
the id, the name, and the status, and the subject form alone. The session
derives the literal from the ticket after the rename. After the commit
`wispy` reads the committed name and `git log -1 --format=%s`. A name
that asks a question, a name past 12 words, or a subject that carries
another name opens one repair turn in the same session: the repair turn
edits the name and amends HEAD. A failure that survives the repair turn
stands, and `wispy` accepts the commit.

The name rule: a name defines the work. It is a short noun phrase or
`<component>: <effect>`, lowercase, with no trailing question mark, with
no interrogative or auxiliary lead word, and at most 12 words.

## The two files

| File | Role |
|---|---|
| `ticket.md` | The contract and the record. Holds the decisions, the results, and the task ticks. |
| `STATE.md` | The handoff for the next session, plus a cache of facts. |

`ticket.md` is the work product. `STATE.md` is working memory. The
split matters:

- A reader of the ticket sees the result, not the search.
- The next session reads 100 lines of state, not 400 lines of ticket.
- A cache line costs one read. It does not become a record.

A cache line carries its sources and its target:

```text
- <fact>. (From: <source>) (Serves: Next)
```

`Serves` is `Next`, `Open`, `task N`, or `cold`. The cut order is a
`cold` line first, then a line that the ticket covers, then the oldest.

## The phases

`wispy run` drives a loop:

1. Set the ticket status to `wip`.
2. Start a work session. Stream it to stdout.
3. Save the answer to `responses/NNN.md`.
4. Distill the session into `ticket.md` and `STATE.md`.
5. After a guard stop, start the next session and go to step 2.

The loop is the answer to the guard stop. `wisp` stops and reports.
`wispy` starts the next session and carries the state.

`.phase` names the open phase. A command that does not match the phase
exits 2. This is the gate: two commands cannot run at once.

## The gates

| Gate | Result |
|---|---|
| No `WISPY_TICKET` | Exit 2. |
| Unresolved ticket id | Exit 2. |
| `steer` with an unfinished commit | Exit 2. |
| `commit` while another phase is open | Exit 2. |
| Skill name with no body | Exit 2. |
| Context guard stop | Exit 75, then the loop continues. |
| `commit`: the committed name asks a question or runs past 12 words | One repair turn, then the commit stands. |
| `commit`: the subject carries another name | One repair turn, then the commit stands. |

A gate that exits costs no tokens, because no model call starts. The
two name checks land after the commit and cost one repair turn each: a
name edit and `git commit --amend` in the same session. A second failure
stands, so the seal never asks a human to amend.

## Ctrl-C

`wispy` installs its own SIGINT handler and reads its own flag. It does
not infer an interrupt from an exit code.

| Command | Marker | Distill | Exit |
|---|---|---|---|
| `run`, `continue`: work | kept | no | 130 |
| `run`, `continue`: distill | kept | retry later | 130 |
| `commit` | kept | no | 130 |
| `steer`, `response` | none | no | 130 only if killed |

The rule: an interrupt never starts a distill turn. The operator
stopped the work. A model call at that moment would cost tokens and
change the record.

The marker lets the next command resume. Nothing is lost.

## One command at a time

`.phase` is a gate, not a lock. Two runs on one ticket at the same time
write one `wisp.jsonl` and lose records. The rule is simple: one
`wispy` command per ticket at a time.
