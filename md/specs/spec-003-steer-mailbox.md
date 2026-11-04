# WISP-003 - Steering: the steer mailbox

- ID: WISP-003
- Date: 2026-09-28
- Status: closed
- Component: `wisp/wisp`
- Source: design review, 2026-09-28; proposal 1 (the steer mailbox) of three
- Depends on: none. Pairs with the round-boundary commit law of `loop_rounds`.

## 1. Background

1. Harness steering queues a message for the model and injects it on a
   pause. The only safe pause in wisp is the round boundary: the last
   round flushed, the jsonl tail stable, the next `llm.turn` not started.
2. `wisp run` holds stdin only for the prompt, so a second message needs
   a side channel. The session dir is already the inter-process
   interface: `wisp.stream`, `wisp.log`, `spill/`.
3. A mid-segment user record is proven: the `continue` record and the
   compaction `CUT_REQUEST` ride the same path, so a steered user record
   needs no wire change.

## 2. Scope

In scope: the `wisp steer` command, the round-boundary drain, the
segment rule, the stale-inbox rule, the end-of-run warning, the stream
and render surface. Out of scope: signals, threads, interruption of an
in-flight `llm.turn` (proposal 3 material).

## 3. Decisions

1. The mailbox is one file: `<DIR>/wisp.steer.inbox`, one JSON line per
   message, `{"content": "..."}`. `wisp steer` appends; messages stack
   in order. No lock, no liveness check.
2. The drain is one atomic rename - the inbox to a consumed name - then
   a read of the consumed copy. An append that lands after the rename
   starts a fresh inbox, so no message is lost and none is read twice.
   A line that fails `json.loads` is a mid-append kill remnant; it is
   skipped, not injected.
3. Each line becomes one user record marked `wisp_steered: True`. It is
   a plain user record on the wire (`message_of` passes it through), it
   commits like any user record, and `wisp grep` finds it.
4. The steered record never opens a segment (`segment_start` skips it)
   and never resets the round counter: steering is not a new segment.
   In a compact session the kept message archives it with the rest of
   the segment.
5. Drain points: the top of every `loop_rounds` iteration (live
   steering), and `run_agent_loop` before the new prompt (a stale inbox
   an earlier run left behind). `wisp continue` needs no extra drain;
   the loop-top drain covers it.
6. The injection order is fixed: drain, append the record, emit one
   `data: {"wisp":"steer",...}` stream line, `flush_records`, then the
   next round. A kill after the drain loses nothing: the record is on
   disk and `wisp continue` resumes it.
7. The end-of-run warning is mandatory: when the run ends - normal
   stop, MAX_TURNS, or a signal - with complete JSON lines still in the
   inbox, `warn_undelivered_steer` writes one stderr warning with the
   count and the inbox path. The inbox stays in place; the next
   `wisp run` drains it before its prompt.
8. Rendering: `wisp render-live` prints the steer payload behind a `[steer]`
   marker line; `records_to_stream` replays a stored `wisp_steered`
   record as the same payload, so `wisp render-past` shows it.

## 4. Rejected alternatives

1. Live stdin (`wisp run --steer`): needs a reader thread and the
   owning terminal; does not compose with the subagent recipes.
2. Signals plus a pid file (the nudge): the interrupt path discards the
   in-flight turn; deferred, not rejected.

## 5. Tests

`tests/test_steer.py`: the queue command, the drain, the segment rule,
the live round-boundary injection, the stale-inbox-before-prompt rule,
the compact-archive rule, the continue-resume drain, the end warning
(through a simulated kill), replay and render, argument parsing, the
wire tag (see section 6).

## 6. Amendment: the wire tag and the segment rule

Accepted after a wording audit found the model cannot tell a steered
message from the turn prompt on the wire: the stored mark
`wisp_steered` never reaches the provider, and the segment-start
wording names two signals ("the prompt of this turn", "the last
'continue' record") a steer can masquerade as.

1. `STEER_TAG` is a one-line tag `build_request` puts before a
   steered user message content: "Steering message added mid-run. It
   is not the turn prompt and it does not open a segment." The stored
   record keeps the user's exact text, so render, grep and the
   compaction archive stay unchanged. The tag is stable per record,
   so request prefixes stay stable.
2. NOTICE and CUT_REQUEST gained one sentence right after the
   segment-start sentence: "A steering message never opens a
   segment." It covers the case the tag cannot: a steer at the kept
   boundary, where the constant text is the only carrier.
3. Terms: the tag and the constants both say "steering message"; the
   stored key stays `wisp_steered`.

Tests: `WireTagTest` in `tests/test_steer.py` (tag on steered
messages only; tag before content, content before NOTICE), and the
steering-segment-rule test in `tests/test_segment_start_wording.py`.

## 7. Amendment 2: the compaction scope wording

Accepted after the segment-rule audit found a second hole: the tag
tells the model what a steering message is not, but no text assigns
the duty to keep it. A mid-segment steer is archived with its
segment by `finalize_segment`; if the kept context drops it, the
directive is silently gone for the rest of the run and every later
`continue`.

1. NOTICE: "every durable fact from your thinking, tool calls, and
   steering messages since the segment start".
2. CUT_REQUEST: "every durable fact from your work and from steering
   messages since the segment start", plus one sentence after the
   segment rule: "A steering message is a directive: keep it and
   follow it." The earlier draft said "arrived late"; dropped
   because the tag defines the message by what it is, and the
   stale-inbox case delivers the steer before the prompt - early,
   not late.
3. ROUND_REMINDER: "Give kept context for the work and steering
   messages since the segment start first". No segment-rule
   sentence: the reminder rides every tool result, and any steer in
   view already carries the tag.
4. "Steering messages", not "user messages": mid-segment user-role
   records are exactly steers and the scaffold CUT_REQUEST, and the
   cut request boilerplate must not be archived as a durable fact.

Tests: the steering-scope and directive-sentence tests in
`tests/test_segment_start_wording.py`.
