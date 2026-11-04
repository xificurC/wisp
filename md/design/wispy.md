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
wispy commit   [--skills LIST] [flags]         [< brief]
wispy response
```

`WISPY_TICKET` is the only binding. It holds a path or an id. An empty,
unset, or unresolved value exits 2 before any model call.

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

A gate exits before a model call. A gate costs no tokens.

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
