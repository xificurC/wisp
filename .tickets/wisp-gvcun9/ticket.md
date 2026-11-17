---
id: 'wisp-gvcun9'
name: 'can wisp render-live stream tool calls?'
status: 'closed'
created: '2026-11-17T13:50:53Z'
parent: null
blocked-on: []
---

## Findings

Scouted `wisp render-live` streaming of tool calls and tool outputs in `wisp/wisp` (single file, line refs below). Verified by reading code and by a synthetic render-live run.

### Current behavior

- The live stream is already line-incremental end to end. `sse_stream` (wisp:4136) writes each raw `data:` SSE line to stdout with flush as it arrives; `Stdio.write` (wisp:121) flushes every write; `render_records` (wisp:1367) renders each stdin line as it comes. Thinking and answer text stream live today.
- Tool calls render in batch for two stacked reasons:
  1. The producer injects one complete `data: {"wisp":"tool_call",...}` line only after the whole model turn ends (`Tools._execute_one`, wisp:2832).
  2. The model's tool-call argument deltas already travel on the stream as raw SSE lines (`delta.tool_calls[].function.arguments` fragments), but `Renderer.chunk` (wisp:4549) renders only reasoning and content fields and drops tool_calls deltas. Confirmed empirically: two delta lines then the inject line produced only the batch header + fenced command.
- Tool outputs render in batch because `Executor.run` (wisp:2509) routes subprocess output into memory/spill and returns it only at process exit; `_execute_one` then injects one complete `tool_result` payload (wisp:2859). The executor's select loop already reads incrementally in 64kB chunks, so the data passes through wisp live; only the emission is batched.

### Can the tool call stream? Yes.

- Option A, renderer-only: teach `Renderer.chunk` to render `delta.tool_calls` deltas. Cost: the raw stream lines carry three provider dialects (openai-chat, openai-responses event shapes, anthropic content_block events), so the renderer would need three parsers, and JSON-escape fragments (`\"` split across deltas) need buffered unescaping. The stream also names no provider (`sse_stream` writes provider lines and `wisp:` lines only), so the renderer must sniff the dialect from event shape. Option A pays a second copy of a normalization that `chunk_of` already owns three lines above the `yield`.
- Option B, producer inject (recommended): `sse_stream` holds the provider-normalized chunk (`chunk_of`, wisp:3927+) before yielding; inject `data: {"wisp":"tool_delta","index":...,"name":...,"arguments_delta":...}` per delta. One dialect, provider-independent. `json_turn` (non-stream mode) degrades to batch, which matches its nature.
- Display: open the `[bash ...]` header when the name delta arrives, stream the command text, close the fence at turn end. `timeoutSeconds`/`maxKilobytes` are model-chosen arguments, so they can stream too once their JSON keys complete.
- render-past parity: `records_to_stream` (wisp:4609) already synthesizes content/reasoning delta lines from stored records; it can synthesize `tool_delta` lines from the stored arguments string the same way.
- Value: the human sees the command while the model writes it and can abort (Ctrl-C) before it runs.

### Can the tool output stream? Yes, with design decisions.

Mechanically easy: give `Executor.run` a callback (or route chunk through `_run_tool`) that injects `data: {"wisp":"tool_output","call_id":...,"content_delta":...}` per read, then the terminal `tool_result` line. The model-facing contract is untouched: the stored record and the model message keep the final complete content, so replay and the byte-stable cache body do not change.

Decisions the scouting raised (all answered 2026-11-17; see Answered gaps and the Implementation record):

1. Status line placement. `Renderer.tool_result` prints `wisp:tool name exit=N ms=M` before the content, the prefix placement settled in `md/design/tool-result-status.md`. exit and ms exist only after process exit. Streaming needs a provisional header (`running...`) plus a final status line, or text first and status after, which contradicts the settled placement.
2. Cap policy. Today the human view equals the model view ("the same text the model receives", help text and Renderer docstring). A live stream can show everything (the human wants to watch a long build) or respect maxKilobytes; the first breaks that stated invariant, the second caps the watch.
3. Attribution. Sequential calls still need `call_id` on each delta so render-live attributes chunks.
4. Backward compatibility. The new marker is additive; old renderers ignore unknown `wisp:` markers only if they skip them — current `render_line` falls through silently, so old render-live binaries stay safe. render-past stays batch (no deltas stored), acceptable as the settled view.
5. Edge cases: timeout/drain_grace partial output must still stream then close; the trailing `\x1b[0m` reset (test_wisp_tool_status pins it) must land after the last delta.

### Effort

- Tool-call streaming: small, about 30-60 lines plus tests (one inject point or one chunk branch, fence state, escape buffering).
- Tool-output streaming: medium, about 100-150 lines plus tests (executor callback seam, delta injects, renderer state machine, provisional header); touches two settled invariants (prefix status placement, human-view-equals-model-view), so it needed a user decision first. The decision and the resulting design record are in `md/design/tool-result-status.md`, section "Live streaming: the fragments lead and the status trails (2026-11-17)".

Line references are into `wisp/wisp` as of commit ab85a65.

### Precedent: how pi streams the same two things

Scouted `~/code/pi` (commit 5f89cc0a7) for the same two questions. pi answers both by normalizing in the client library, never in the display.

- pi's LLM client (`packages/ai`) maps every provider stream into one typed `AssistantMessageEvent` (`packages/ai/src/types.ts:831-841`) with `toolcall_start`, `toolcall_delta`, `toolcall_end`. The provider adapters pay the dialect cost once each (`api/openai-completions.ts:450`, `api/anthropic-messages.ts:1046`, `api/openai-responses-shared.ts:530`, `api/google-generative-ai.ts:213`, `api/bedrock-converse-stream.ts:681`, `api/mistral-conversations.ts:730`, `api/pi-messages.ts:273`). No display code reads a provider payload.
- Tool call: `agent-loop.ts:440` forwards those events as `message_update`; `modes/interactive/interactive-mode.ts:3654` creates a `ToolExecutionComponent` on the first `message_update` carrying a `toolCall` block and calls `updateArgs()` on each later one, so the command draws while the model writes it. Partial arguments are a parsed object: `durable/src/harness/partial-changes.ts:64` feeds `StreamingJsonParser` with each `toolcall_delta`. pi pays the split-fragment cost once, in the parser.
- Tool output: each tool takes an `onUpdate` callback (`core/tools/bash.ts:293`), throttled at 100 ms (`core/tools/renderers/bash.ts:19`), carrying a snapshot bounded to 2000 lines / 50 KB (`core/tools/truncate.ts`) plus the path of the full output in a temp file. The durable harness publishes the same shape as a `ToolSlot` with `status` and a bounded `output` plus `droppedBytes`/`droppedLines`, on a throttled commit (`durable/src/harness/live.ts:24-40`, `durable/src/harness/tool.ts:951`).
- Out-of-process consumers get a JSONL protocol derived from the normalized events, never from provider SSE: `modes/json-event.ts` strips the cumulative snapshots and keeps the deltas; `docs/json.md` documents `toolcall_delta {contentIndex, delta}` and `tool_execution_update {toolCallId, partialResult}`.

What the precedent settles for the Gaps below: pi picks Option B's shape wherever a display sits outside the producer, and pi resolves the cap question in favor of the bounded window plus a pointer to the full text, for the human view and the model view alike. pi does not settle the status-placement question, because pi re-renders a whole TUI block and appends elapsed time at the end, which an append-only line renderer cannot do.

## Answered gaps (2026-11-17, user decision)

- **Build it, by Option B.** Tool-call streaming ships as a producer-injected `wisp:tool_delta` marker built from the provider-normalized chunk in `sse_stream`, not as renderer-side parsing of raw provider deltas.
- **Status placement: at the end.** A tool result's `wisp:tool` status line prints after the content. Live output arrives first, so the status closes the block. The model-facing tool text keeps the prefix placement settled in `md/design/tool-result-status.md`; the human renderer and the model wire now differ in order.
- **Cap policy: respect `maxKilobytes`.** The stream carries only the bytes that enter the model-facing head. The spill tail never streams. The status line then reports `bytes`, `offset`, `rest_kb`, and `spill`, so the human learns where the rest lives.

## Gaps

None. Implemented and tested; see the implementation record below.

## Implementation record (2026-11-17)

Two additive stream markers; an old renderer skips both, because `render_line` falls through on an unknown `wisp:` marker.

- `data: {"wisp":"tool_delta","index":0,"id":"call_1","name":"bash","arguments_delta":"{\"comm"}`: one marker per provider-normalized fragment, injected by `sse_stream` from `tool_deltas_of(chunk)` right after `chunk_of`. The three dialects are merged before the marker, so the renderer reads one shape.
- `data: {"wisp":"tool_output","call_id":"call_1","content_delta":"hi\n"}`: one marker per head chunk, injected by `Tools._run_tool` through the new `Executor.run(..., on_head)` seam. The bytes decode through an incremental UTF-8 decoder; the spill tail never reaches `on_head`, so the stream is capped at the call's `maxKilobytes`.

Human render shape:

```
```
echo hi
```
[bash 5s 5kb]

hi
wisp:tool bash exit=0 ms=43
^[[0m
```

- `Renderer.tool_delta` opens the fence on the first fragment and appends only the new text decoded from the partial JSON: `command` for bash and python3, `path` for load_image, raw arguments otherwise (`decode_json_prefix`, `json_string_value_start`, `display_key_of`). An escape split across fragments is not consumed until its tail lands.
- `Renderer.tool_header` completes a drawn command, closes the fence, and writes the tag line. The tag trails because `timeoutSeconds` and `maxKilobytes` are model-chosen arguments that complete only with the fence.
- `Renderer.tool_output` streams the head; `Renderer.tool_result` skips content it already streamed and closes with the `wisp:tool` status line and the SGR reset, so the reset lands after the last streamed byte.
- render-past is unchanged. `records_to_stream` emits no deltas, and the same two renderer methods draw the same text from stored fields, so the tool blocks of a live run and its replay are byte-identical. The one difference is the `[user]` prompt block `render-past` adds, which predates this change (verified with `diff -u` on a run through `tests/fixtures/fake_llm_sse.py tworound`).

Invariants changed, by explicit user decision:

- The human render no longer prints "the same text the model receives". The model wire keeps the prefix status (`tool_text_of`); only the renderer's order changed.
- `md/design/tool-result-status.md` records the old tag-first human shape; its closing section records the new shape for 2026-11-17.

Tests:

- New `wisp/tests/test_stream_render.py`, 16 cases: dialect mapping, `sse_stream` injection, partial-JSON decode across split escapes and a split surrogate pair, call and output rendering, the `maxKilobytes` cap on `on_head`, and the `tool_output` to `tool_result` wiring.
- Updated `wisp/tests/test_tool_result_reset.py` (status before the reset) and `tests/test_wisp_tool_status.py` (renderer shape, `FakeExec.run` signature).
- `python3 -m pytest wisp/tests tests -q`: 188 passed, 1 failed. The failure is `test_attachments.TestChatGoldenBody::test_golden`, which pins the old python3 tool description; it fails on HEAD `ab85a65` too.
- `tests/test_wisp_run_nonstream.sh`: 5/5. `tests/test_wisp_per_round_commit.sh`: 4/4.

### Second pass: one `wisp:tool` line per call (2026-11-17, later the same day)

The user read the shape above and rejected two trailing metadata lines per call. The tag line is gone; one line closes the block:

```
```
echo hi
```

hi
wisp:tool bash timeoutSeconds=5 maxKilobytes=5 exit=0 ms=43
^[[0m
```

- `tool_text_of(rec, budget=())` gained the optional budget tuple. It inserts the tokens between the name and `exit=`. The model wire passes nothing, so its prefix header still derives from the record alone; the record never stores the requested limits.
- `Renderer.tool_header` writes only the fence, parks `timeoutSeconds` and `maxKilobytes` on `Renderer._budget`. A call with no command and no drawn fence (`load_image` with a bad path) draws nothing and spends no separator line.
- `Renderer.tool_result` passes the parked budget and clears it. A bare `tool_result` with no preceding header prints the old line with no budget.
- `timeout_s=` keeps its meaning: the timeout that fired. `timeoutSeconds=` is the limit the call asked for; on a timeout both carry the same number.
- render-past parity holds: `records_to_stream` emits the stored `tool_call` payload, which parks the same budget, then the stored result, which closes with the merged line. `diff -u` on a `tests/fixtures/fake_llm_sse.py tworound` run differs only in the `[user]` block render-past adds.
- Tradeoff accepted by the user: while a command runs, no status line describes it until the process exits.

Tests updated for the merged shape: `wisp/tests/test_stream_render.py`, `tests/test_wisp_tool_status.py`, `tests/test_tool_result_reset.py` (no change needed: its payloads carry no header), `tests/test_wisp_run_nonstream.sh` and `tests/test_wisp_per_round_commit.sh` (the render-past grep now looks for `wisp:tool bash ` instead of `[bash `).

Verification: `python3 -m pytest wisp/tests tests -q` gives 188 passed, 1 failed (the same pre-existing golden); the two shell suites are 5/5 and 4/4; the other three shell suites unchanged at 1/1, 11/11, 12/12.

Answer to the user's two checks: the command does stream, one `tool_delta` per provider-normalized argument fragment, so the fence grows while the model writes; and `echo hi; sleep 60; echo bye` prints `hi` immediately and `bye` after 60s, because bash's `echo` builtin writes with a raw syscall. A piped program that uses stdio buffering (python3's `print`, `cat`, `grep`) prints nothing until its buffer fills or the process exits; `PYTHONUNBUFFERED=1`, `stdbuf -oL -eL`, or `--line-buffered` in the command forces line buffering.

### Third pass: the call fence names the tool (2026-11-17)

The user asked to put "```bash" and "```python3" as the tool call fence
headers, so the block is easier to find in the render. The fences in the
shapes quoted above are plain; this section records the shipped shape:

````
```bash
echo hi
```

hi
wisp:tool bash timeoutSeconds=5 maxKilobytes=5 exit=0 ms=43
^[[0m
````

- New `fence_of(name)` (wisp/wisp, next to `display_key_of`): `` ```bash ``
  for bash, `` ```python3 `` for python3, the plain `` ``` `` for every
  other name, because `load_image` draws a path and an unknown tool
  draws raw arguments.
- `Renderer.tool_delta` now opens the fence at the first fragment that
  carries the name, not at the first fragment. The call dict gained
  an `opened` flag. A wire that sends arguments before the name keeps
  the fragments in `raw` and draws them when the name lands; a call
  that never learns its name draws no fence.
- `Renderer._close_call` closes a fence only when `opened` is set.
  `tool_header` discards an unopened parked call and draws the whole
  block from the inject payload, tagged with `fence_of(name)`, so a
  nameless call still renders correctly.
- The closing fence stays plain. Replay and live stay byte-identical:
  `records_to_stream` emits the stored `tool_call` payload and
  `tool_header` opens the block with the same `fence_of(name)`.
- Help texts for `render-live` (module docstring line ~38 and the
  `render-live` help entry) now say the fence is tagged.
- Two calls in one turn draw both tagged fences before either output,
  because both calls' deltas arrive in the one assistant response and
  `tool_header` follows the results. That order predates this change;
  it is the wire order, not a renderer regression.

Tests: `wisp/tests/test_stream_render.py` gained four cases (python3
tag, name trailing the first fragment, a nameless call drawing no
fence, a nameless call still drawing from the inject) and four
existing expectations moved to the tagged fence; the `load_image` case
keeps the plain fence. `tests/test_wisp_tool_status.py` moved its bash
fence expectation to `` ```bash ``.

Verification: `python3 -m pytest wisp/tests tests -q` gives 192 passed,
1 failed (the same pre-existing `test_attachments` golden that pins the
old python3 tool description); `tests/test_wisp_run_nonstream.sh` 5/5;
`tests/test_wisp_per_round_commit.sh` 4/4. A live `tworound` run through
`tests/fixtures/fake_llm_sse.py` renders `` ```bash `` and its
`diff -u` against `render-past` differs only in the `[user]` block that
predates this change.

### Fourth pass: the argument freeze is the endpoint's chunking (2026-11-17)

The user saw a tool call draw its first characters, stall for a couple
of seconds, then land the rest in one large chunk. Tested, and the
stall is upstream of wisp.

Method: a probe POSTs the same streaming chat body straight to
`WISP_LLM_URL` with urllib and timestamps every `data:` line as it is
read off the socket, so wisp is not in the path
(`wisp-sessions/wisp-gvcun9-006/probe/provider_timeline.py`). A second
run pipes `wisp run` through `wisp render-live` and byte-stamps the
renderer's stdout (`probe/stamp_bytes.py`).

Result, prompt asking for one bash call whose command is a 6.5 kB
heredoc, model `deepseek-v4.1-flash`, no thinking:

```
 17.669 + 0.045 tool_call name=bash args=''
 17.699 + 0.030 tool_call args='{"command": "'
 17.712 + 0.013 tool_call args="cat <<'EOF' > /tmp"
 22.735 + 5.023 tool_call args="/wisp-probe-big.txt\nline 01: ..."   # 6.6 kB
 22.750 + 0.015 tool_call args='"}'
```

Five argument fragments, one 5.0 s gap, and the whole 6.6 kB body in
the fragment after the gap. The same shape held with thinking
(`reasoning_effort=xhigh`, 6.7 s gap) and without
`stream_options.include_usage` (5.0 s gap). A nonce in the prompt
defeats LiteLLM's response cache, which otherwise replays a whole turn
as one chunk.

The renderer passes the timing through. A 790-byte heredoc run wrote
the fence at 0.840 s, `cat <<'EOF' > /tmp` at 0.900 s, the rest at
2.169 s (a 1.27 s stall); the raw `wisp run` stream stamped 1.015 s and
2.269 s for the same two fragments, off by milliseconds.

Same endpoint, same prompt, other local models:

| model | argument fragments | longest gap | longest fragment |
| --- | --- | --- | --- |
| deepseek-v4.1-flash | 5 | 5.02 s | 6.6 kB |
| glm-5.3-flash | 1633 | 0.19 s | 20 B |
| qwen3.8-27b | 455 | 1.31 s (one pause) | 20 B |
| mimo-2.6-flash | 1720 | 0.07 s | 20 B |
| laguna-s-2.1 | 1812 | 0.07 s | 20 B |

So the coarse chunking is a property of the `deepseek-v4.1-flash` path
on the company LiteLLM endpoint, not of wisp. That model streams its
reasoning at ~15 ms per fragment (1122 fragments in one run) and its
answer text in small fragments, so the buffer sits on the tool-call
argument path only.

The visible "first characters" are the endpoint's one early fragment:
`{"command": "` decodes to empty text, so the drawn prefix is whatever
that early fragment carried (`cat <<'EOF' > /tmp` above). The renderer
then holds the fence until the next fragment lands.

No wisp change follows. The pipeline is byte-incremental end to end,
and only the endpoint can send finer fragments.
