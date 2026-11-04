# Steering

Steering adds a message to a run that is already going. The message
reaches the model at the next safe point, and no message is lost.

## The shape

`wisp steer -d DIR` reads stdin whole. It appends one JSON line to
`<DIR>/wisp.steer.inbox`. It does not touch the session.

A live `wisp run` drains the inbox at each round boundary. Each line
becomes a user record marked `wisp_steered`. The stream gets one
`data: {"wisp":"steer"}` line per message.

## Three rules

### Rule 1: one side channel, not a second stdin

`wisp run` holds stdin for the prompt. A second message needs another
path. The session dir is already the interface between processes.

The inbox file gives three properties for free:

- a write is atomic for one line;
- a reader can drain it without a lock;
- a writer needs no knowledge of the run.

### Rule 2: drain at a round boundary only

A round boundary is the only safe point to add a record. The tail is
stable and the next request has not started.

Steering never opens a segment. It never resets the round counter. A
steered record is a user record in the current segment.

### Rule 3: no liveness check

`wisp steer` does not check whether a run is live. A check would race
with the run. A check would also fail for a run that starts a moment
later.

So a message can land in a dir with no run. That is a feature. The next
`wisp run` drains the inbox before its own prompt.

## The stale-message hazard

A queued message can become stale. The run may finish its work before
the message arrives. The message then lands in a session where the
work is done.

wisp cannot detect this. It does not read the message. It warns on
stderr when messages still wait at the end of a run, and it drains them
at the start of the next run.

The operator sees the warning and decides. A wrapper can turn the
warning into a gate.

## Steering versus the prompt

| Path | When | Effect |
|---|---|---|
| `wisp run < prompt` | At start | Opens a turn. Appends one user record. |
| `wisp steer < message` | During a run | Adds a user record at the next round boundary. |

Both end in a user record. Only the prompt opens a segment.

## Why not interrupts

An interrupt would stop the round in the middle. The round would have
no tool results, so the commit rule would reject it. The operator would
lose the work of the round.

A queued message costs one round of delay. It loses nothing.

## The stream marker

The marker line exists so a renderer can show the steer point without
parsing the record. A reader of `wisp.jsonl` sees the same event as a
user record with the `wisp_steered` flag.
