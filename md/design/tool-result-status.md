# Tool result status: exit code, duration, and truncation for the model

A tool call knows more than its output. The call knows the exit code,
the duration, the total byte count, whether the harness truncated the
output, and where the full output lives. The model learns none of
these facts today. The model receives `content` alone: raw output plus
a prose note when the harness truncated or timed out.

The first design pass asked one question: which channel carries the
exit code and duration. This pass asks four questions, because the
channel is four independent choices:

1. **Placement.** Do the facts sit before the output, after the output,
   on both ends, or in-band at the point of failure?
2. **Encoding.** Prose, namespaced `key=value`, JSON, a sectioned
   block, or a bare delimiter?
3. **Delimitation.** Is the output itself bounded, and by what?
4. **Protocol location.** Does each call carry the recovery prose, or
   does the system prompt carry the protocol once and the result carry
   only fields?

The four choices are independent. A prefix header can be prose or
JSON. A JSON line can lead or trail. A sectioned block can be the
encoding and the delimitation at the same time. The rest of this
document separates the choices, names the designs that combine the
choices, and recommends one combination.

## What the model sees today

All three wire mappers build the tool message from `rec["content"]`
alone:

| dialect | function | field |
|---|---|---|
| openai-chat | `message_of` (3432) | `content` |
| openai-responses | `items_of_responses` (3470) | `output` |
| anthropic | `items_of_anthropic` (3526) | `tool_result.content` |

`Tools._execute_one` (2778) puts `"exit"` into the stdout payload
(2818) and the record. `records_to_stream` (4554) replays the same
payload for `render-past`. `Renderer.tool_result` (4517) writes the
🟢/🔴 dot line. The model sees none of that path.

Duration exists once, inside the `safe_log` call at line 2813. wisp
computes the number and throws the number away. The clock at line 2783
is `Clock.ms()`, which reads wall time; the executor deadline uses
`Clock.monotonic()` (2495). A model-facing duration must use `Clock.monotonic()`.

The truncation fact exists only as prose appended by `_run_tool`
(2876): `---\nTool call notes:\n<note>`. The fence fires only in
`_run_tool`. A `load_image` result and a bad-argument result set
`content` and `exit` with no fence. A spilled command and a timed-out
command carry the fence. A successful command with empty output
produces `content == ""`, so the model receives a tool message with no
text at all.

## What the sealed run showed

The sealed run gives one direct observation about placement and one
about coverage.

**Placement.** Ten spill notes fired in three runs (kv 7, react 2, vf2
1). The model read no spill file. More telling: in every case the
model's next call followed the visible head. On kv event 6 the model
re-dumped a narrower address range instead of reading the tail the
note pointed at. On react event 15 the model fixed the build from the
21 visible error lines without touching the tail. On vf2 event 16 the
model wrote its own C engine from the visible header. The note sat at
the tail, after the head the model was already acting on. The tail
was not unreadable; the tail was not where the next action formed.

Treat that as local evidence, not as a law about transformers. The
tool message is about 5 kB, so both ends sit near an edge; the middle
is the risky region, not the ends. The observation says the model
frames the head as "the result" and the tail as "a note about the
result". A line before the result changes the frame; a line after the
result inherits the note frame.

**Coverage.** The dangerous combination is truncation plus a text-free
failure. `items_of` builds `{"role":"tool","content":content}`, and
the 🟢/🔴 dot exists only in the human renderer. A command whose only
error line fell past the cap leaves the model with a silent, complete
looking head. The sealed run escaped that case by the luck of message
ordering. The design must close the case by construction.

**Cost.** 221 tool calls, 10 of them spilled. The current prose spill
note runs 300 to 400 bytes per spill. The fence line runs about 20
bytes per spill. The current total is roughly 4 kB.

## Constraints

1. **The truncation fact must precede the truncated head.** A model
   that reads the first 5 kB and does not know the output was cut
   cannot recover the cut from the head. This constraint decides
   placement on its own.
2. **The fence can be forged.** A command that greps wisp's own source
   prints `Tool call notes:` verbatim. The model cannot tell harness
   text from output text by the fence string alone.
3. **`Clock.ms()` is wall time.** A clock step can make a `ms()`
   difference negative. Use `Clock.monotonic()` for a model-facing duration.
4. **Exit 1 is normal for `grep` and `diff`.** Report the fact. Never
   report the judgment "failed".
5. **124 is wisp's code.** The timeout explanation belongs in one
   place. A status line must not contradict that place.
6. **Replay.** Every round rebuilds the wire from stored records. Text
   baked into `content` is stored forever. Text derived at wire time
   needs a stored field and reproduces on every resume.
7. **Cache.** The serialized body must stay byte-stable across fresh
   and resumed runs. A derived header is stable when its fields are
   stable.
8. **Cost.** 221 calls in the sealed run. Every byte in the header is
   paid 221 times.
9. **Dialect parity.** openai-chat, openai-responses, and anthropic
   share one model-facing convention, or the model learns three
   conventions. Only anthropic has a native error flag.

## Decision 1: placement

| placement | shape | wins | loses |
|---|---|---|---|
| prefix | facts, then output | truncation known first; position authenticates the facts; the next action forms after the facts | output no longer starts at message byte 0; a paste from byte 0 carries the header |
| suffix | output, then facts | output stays pristine; the human record stays raw | the truncation fact arrives after the head; inherits the tail-note frame |
| bracket | facts, output, close marker | both boundaries; a forged tail cannot pass the close marker | two lines of overhead; the close marker is still text |
| in-band | facts only at the failure point | zero cost on success | the model cannot know a success was truncated; placement is unpredictable |
| per-round | one digest after a batch | cheapest per call | breaks result adjacency; the batch may not exist |

The evidence line above decides prefix for the truncation and exit
facts. A close marker is a separate, optional choice.

## Decision 2: encoding

| encoding | example | bytes/call | strengths | weaknesses |
|---|---|---|---|---|
| prose | `wisp: exit 1 in 2310ms` | about 22 | reads as a sentence; the harness already uses `wisp:` | no room for structured fields without a sentence per field |
| namespaced KV | `wisp:tool bash exit=1 ms=2310` | about 30 | compact; greppable; field order is a stable grammar | values with spaces need quoting |
| JSON line | `{"wisp":{"name":"bash","exit":1,"ms":2310}}` | about 65 | unambiguous bounds; handles any value; machine-parseable | token-heavy; invites "parse the data" behavior |
| sectioned block | `=== METADATA ===\nexit: 1\n...` | about 90 | maximally readable; explicit section names | boilerplate on every call; the model skims fixed headings |
| bare delimiter | `---` alone, facts elsewhere | about 4 | cheap | carries no facts; the current fence is this, and it is forgeable |

Four encodings look plausible and lose on contact:

- A code fence around the status collides with output that contains
  code fences and adds no fact the KV line lacks.
- An XML tag (`<wisp exit="1" ms="2310"/>`) is unambiguous and
  model-familiar, but it collides with XML and HTML output and costs
  more than the KV line.
- YAML front matter (`---`, then fields, then `---`) collides with the
  current `---` fence and with Markdown.
- A comment line (`# wisp: ...`) collides with every language that has
  comments.

The KV line and the JSON line differ by about 35 bytes, which is about
8 kB over 221 calls. Neither dominates. KV wins on compactness and on
reading as a status line. JSON wins on arbitrary values, especially
paths with spaces or quotes, and on machine parsing by wisp itself.

A version tag (`wisp:tool/v1`) costs 3 bytes and pins the grammar
before the first field is added. Worth it.

## Decision 3: delimitation

The output can be raw, closed by a sentinel, or bracketed by two
markers.

- **Raw output after a prefix header.** The header is the open marker.
  The output ends at the end of the message, which is the next turn.
  Cheapest. Nothing marks a cut, but the header already says
  `spill=...` when a cut happened.
- **Close sentinel.** A final `wisp:end` line. It lets a reader tell a
  complete output from a truncated one, and it makes a forged
  `wisp:tool` line inside the output harmless, because the true header
  is first and the true close is last. Costs about 10 bytes.
- **Open and close headings.** `=== TOOL CALL OUTPUT ===` and
  `=== END TOOL CALL OUTPUT ===`. Maximally explicit. The open heading
  delays the first output byte and adds boilerplate the model may
  learn to skip.

The close sentinel is the only delimitation that pays for itself. The
headings pay only if the user wants a human-readable section shape in
the transcript.

## Decision 4: protocol location

Today each spilled call carries the full recovery prose: the spill
path, the offset, the rest size, and two alternative commands. That is
300 to 400 bytes, repeated per spill, at the tail.

The alternative moves the protocol into the system prompt once and
leaves machine facts in the header:

```
A result with spill="..." was truncated. Read the rest with
tail -c +<offset> <spill-path>. Set maxKilobytes=rest_kb on a new call
to read the rest in one piece. Spill files are never deleted.
```

The prompt costs about 250 bytes per session. The header costs about
60 bytes per spill. At 10 spills, the split saves about 2 kB and puts
the protocol where the model reads it before the first tool call.

The risk: a model that ignores the system prompt ignores the protocol.
The counter-risk today: a model that ignores the tail ignores the
protocol. The system prompt is the more reliable of the two locations.

## How the request's ideas map

- **"Structured, JSON"** is an encoding choice (Decision 2). Solution 5
  is the JSON line. The JSON line and the KV line are the same design at
  two encodings.
- **"Before or after"** is a placement choice (Decision 1). The sealed
  run's next-call behavior favors before. A trailing line inherits the
  note frame the model already skips.
- **"METADATA, then TOOL CALL OUTPUT"** is an encoding plus a
  delimitation choice. Solution 6 is that shape. The shape is the
  clearest for a human reader and the most expensive for the model.
- **"An output marker or heading"** is a delimitation choice (Decision
  3). A close sentinel (Solution 7) is the cheap version. An open
  heading (Solution 6) is the clear version.

The four ideas cover three of the four decisions. The missing decision
is protocol location, and it controls most of the byte cost: per-call
recovery prose is the reason today's tool text is large.

## The designs

### Solution 1: the notes fence gains a status line

The status becomes the first line inside the existing fenced block.

```
<5000 bytes of head>
---
Tool call notes:
Result: exit 1 in 2310ms.
Output greater than maxKilobytes=5. Full output written to: ...
```

The fence now fires on every call. Empty output yields a message with
the fence alone. Costs: a fence and a line on every call, and the
status sits at the tail.

### Solution 2: a `wisp:` status trailer at wire time

One helper appends the status to the tool text.

```
<5000 bytes of head>
---
Tool call notes:
Output greater than maxKilobytes=5. Full output written to: ...

wisp: exit 1 in 2310ms
```

A call with no output renders as the status line alone. `content` in
`wisp.jsonl` stays raw. The status is the last line of the visible
head.

### Solution 3: severity-routed status

Success stays silent. Failure leads.

```
exit 0, no spill      -> message unchanged
exit 0, spill         -> message ends with the notes fence
exit 0, slow call     -> "wisp: 4900 of 5000ms used" appended
exit != 0, output     -> "wisp: exit 1 in 2310ms.\n---\n" then the head
exit != 0, no output  -> "wisp: exit 1 in 12ms; no output."
```

The failure line leads because a failure is the case where the output
is most likely long, spilled, or absent. Success reports no duration,
so the model cannot compare a warm path with a cold path.

### Solution 4: prefix status header, anomaly fields only

One line before the output. The base line carries the facts that are
always true: name, exit, duration. The anomaly fields appear only when
they apply.

```
wisp:tool bash exit=0 ms=431
<output>
```

```
wisp:tool bash exit=1 ms=2310 bytes=12000 offset=5001 rest_kb=7 spill="/home/u/proj/wisp-sessions/s1/spill/7cwfhu3d"
<5000 bytes of head>
```

```
wisp:tool bash exit=124 ms=5001 timeout_s=5
<partial output>
```

```
wisp:tool bash exit=1 ms=12 bytes=0
```

```
wisp:tool load_image exit=0 ms=42
Loaded image: page-3.png (image/png, 184320 bytes).
```

Properties:

- The truncation fact is the first line, so the model knows the head is
  incomplete before the model trusts the head.
- The base line is about 30 bytes. A spill line is about 100. The
  run total is about 7 kB for 221 calls, against about 4 kB today.
- The header fires on every record: bash, python3, load_image, unknown
  tool, bad arguments. The empty-output hole closes by construction.
- Position is authentication. The prompt says "the first line of every
  tool result is harness status; everything after it is output." A
  command cannot print before its own output, so a forged `wisp:tool`
  line lands after the true header and reads as output.
- The protocol lives in the system prompt once, so no per-call prose.
- `content` in `wisp.jsonl` stays raw. The header is derived from
  `name`, `exit`, `ms`, `bytes`, `offset`, `rest_kb`, `spill`,
  `timeout_s`, and `abandoned`. Old records without `ms` render
  `wisp:tool bash exit=1` and no duration.
- The header carries no judgment. `exit=1` is a fact; `grep` exit 1
  reads as a fact.

Costs:

- Output no longer starts at message byte 0. A model that pastes from
  byte 0 pastes the header. The header is one line, and the spill
  offset still points at the true output.
- The header is still text. A command that prints `wisp:tool ...` can
  imitate the format, but cannot imitate the position.

### Solution 5: prefix JSON metadata line

One JSON object on the first line, raw output after it.

```
{"wisp":{"v":1,"name":"bash","exit":1,"ms":2310,"bytes":12000,"offset":5001,"rest_kb":7,"spill":"/home/u/proj/wisp-sessions/s1/spill/7cwfhu3d"}}
<5000 bytes of head>
```

Properties:

- Unambiguous field bounds. A path with spaces, quotes, or newlines
  needs no quoting rule.
- wisp itself can parse the line without a second grammar.
- The model has a strong JSON prior, which cuts both ways: the model
  parses the line reliably, and the model may treat the line as data
  to inspect rather than as status to act on.
- About 65 to 100 bytes per call, so about 20 kB over the run. The
  difference from Solution 4 is real but small against the context.

The JSON line and the KV line are the same design at two encodings.
The choice is a preference, not an architecture.

### Solution 6: sectioned envelope

```
=== METADATA ===
name: bash
exit: 1
duration_ms: 2310
output_bytes: 12000
spilled: /home/u/proj/wisp-sessions/s1/spill/7cwfhu3d
rest_kb: 7
=== TOOL CALL OUTPUT ===
<5000 bytes of head>
=== END TOOL CALL OUTPUT ===
```

Properties:

- The clearest human shape and the clearest boundary. The section names
  do exactly what the user asked: they delineate metadata from output.
- The most expensive shape, about 90 to 130 bytes per call, and the
  fixed headings repeat 221 times.
- The open heading carries no facts. A model that skims to the first
  line of output still learns nothing about truncation until it reads
  the metadata block.
- The section idea collapses into Solution 4 when the metadata fits
  one line. The headings buy readability, not salience.

### Solution 7: bracketed output

Solution 4 plus a close sentinel.

```
wisp:tool bash exit=1 ms=2310 bytes=12000 offset=5001 rest_kb=7 spill="..."
<5000 bytes of head>
wisp:end
```

Properties:

- The prefix carries the facts. The sentinel marks the true end.
- A forged `wisp:tool` line inside the output is harmless: the true
  header is first, the true close is last.
- A truncated head still ends with `wisp:end`, which could mislead a
  model into reading the sentinel as "complete". The header says
  `spill=...`, so the two lines must be read together. The sentinel
  word should be neutral (`wisp:end`), not `wisp:complete`.
- A per-session nonce on both markers (`wisp:tool#7f3a`, `wisp:end#7f3a`)
  makes an accidental collision impossible. The nonce does not stop a
  deliberate forgery, because the model knows the nonce from the
  system prompt.
- About 10 bytes per call.

### Solution 8: trailing sentinel only

Drop the notes fence, keep the facts at the tail.

```
<5000 bytes of head>
--- wisp: exit 1 · 2310ms · 12000B · spill=/... · rest_kb=7 ---
```

Properties:

- The smallest change from today. The prose note becomes one line.
- Output stays at byte 0. The human record stays raw.
- Inherits the tail-note frame from the sealed run: the model acts on
  the head and does not attend to the line after it.
- Truncation is still learned after the head is read. A model that
  stops at the cap never sees the line.
- The forge problem is weakest here: a command's own trailing text can
  sit where the true trailer sits.

### Solution 9: native dialect channels

Use the provider's structure instead of, or in addition to, text.

- **Anthropic `is_error`.** `tool_result` takes a boolean. Set it for
  the codes the harness owns: 124, unknown tool, bad arguments. Do not
  set it for a plain nonzero exit: `grep` exit 1 is a working command,
  and `is_error: true` would tell the model the tool failed.
- **Content-block parts.** Anthropic `tool_result.content` and
  openai-responses `function_call_output.output` accept a list of
  blocks. Put the status in one text block and the output in a second
  block. The block boundary is real structure, not a string marker.
  openai-chat flattens tool content to a string, so the convention
  breaks on one dialect.
- **No native field in openai.** openai-chat has no status field on a
  tool message, and openai-responses `function_call_output` has none.

The native channels are riders, not the channel. They cannot carry the
duration in two of three dialects, and `is_error` cannot express
"nonzero but normal". The text header stays the baseline; `is_error`
is a bonus where the dialect has it.

### Solution 10: per-round status digest

One status block after all results of one assistant turn, listing each
call. Cheapest per call when the model batches calls. Costs: a
synthetic message, a break in result adjacency, and an empty digest
when the model makes one call. wisp's tools run sequentially in block
order, so per-call headers fit the existing shape with no new message.

### Solution 11: out-of-band status

A separate `tool_status` record, or a synthetic user message after each
result. The model can ignore a message the model does not expect, and
the dialect mappers must invent a role for the record. Reject.

## Evaluation

| design | facts on success | truncation before head | output at byte 0 | forge resistance | empty output visible | stored in jsonl | old-record replay | bytes/call | dialect parity |
|---|---|---|---|---|---|---|---|---|---|
| S1 fence line | yes | no | yes | fence string only | yes | yes | no status | about 45 | yes |
| S2 trailer | yes | no | yes | weak | yes | no | `wisp: exit N` | about 25 | yes |
| S3 routing | no | no | yes (success) | weak | yes | yes | no status | 0 to 25 | yes |
| S4 prefix header | yes | yes | no | position + namespace | yes | no | header from `exit` | 30 to 100 | yes |
| S5 JSON line | yes | yes | no | position | yes | no | header from `exit` | 65 to 105 | yes |
| S6 sections | yes | yes | no | position + headings | yes | no | header from `exit` | 90 to 130 | yes |
| S7 bracket | yes | yes | no | position + close | yes | no | header from `exit` | 40 to 110 | yes |
| S8 trailer sentinel | yes | no | yes | weakest | yes | no | `wisp: exit N` | 45 | yes |
| S9 native fields | partial | depends on text | depends | provider-managed | no | no | no | 0 to 30 | no |
| S10 round digest | yes | yes | yes | position | yes | no | header from `exit` | 30 / batch | yes |

"Stored in jsonl" means the status text lives in `content`. Every
design except S1 stores fields and derives the text. That is the right
split: the record keeps facts, the wire keeps wording.

## Recommendation

**Solution 4, with three optional riders: the Solution 7 close
sentinel, the Solution 9 `is_error` flag, and the Solution 3 empty
case folded into the header.**

Why Solution 4:

1. **The sealed run decides placement.** The model's next action
   followed the head in all ten spills. A truncation fact at the tail
   arrives after the model has already chosen the next call. A prefix
   header puts the fact before the choice.
2. **Position is the answer to the forge problem.** The fence is
   forgeable because it is a string at an unpredictable place. The
   first line of a tool result is not forgeable: a command cannot print
   before its own output. The prompt states the one-line rule, and the
   rule holds for every dialect.
3. **One line closes the empty-output hole.** Every record gets a
   header, including a record with no output and a bad argument list.
   The model never receives a text-free tool message.
4. **The protocol belongs in the prompt once.** The per-call prose is
   the largest part of today's tool text and the least attended part.
   The header carries fields; the prompt carries meaning. The split
   cuts bytes and moves the protocol to where the model reads it
   before the first call.
5. **The record keeps facts.** `content` stays raw, so `grep` and
   `render-past` see the command's bytes. The header is derived, so a
   resumed session labels old rounds consistently.

Why not the alternatives:

- **S5 JSON line** is the same design with a heavier encoding. Take it
  if the user wants wisp to parse the line or if spill paths with
  spaces and quotes are a real risk. The model reads both encodings
  well.
- **S6 sections** buys readability for humans and costs the most
  bytes. The headings do not add a fact the one-line header lacks.
- **S7 bracket** is a cheap rider, not a replacement. Add the close
  sentinel if the transcript should show where output ends.
- **S8 trailer only** repeats the sealed run's failure mode. Reject.
- **S3 routing** hides the duration on success, which is the fact the
  user asked to expose.
- **S9 native fields** cannot carry the facts in two of three
  dialects. Use `is_error` as a bonus where it exists.

### The wire grammar

```
wisp:tool <name> exit=<code> ms=<duration>[ <anomaly fields>]\n<output>
```

Fields:

| field | when | meaning |
|---|---|---|
| `name` | always | `bash`, `python3`, `load_image` |
| `exit` | always | the process exit code; a fact, not a verdict |
| `ms` | always when measured | monotonic duration in milliseconds |
| `bytes` | on spill or empty output | total output size in bytes |
| `offset` | on spill | the first byte after the returned head, for `tail -c +<offset>` |
| `rest_kb` | on spill | the `maxKilobytes` value that returns the rest in one call |
| `spill` | on spill | the spill file path, JSON-quoted |
| `timeout_s` | exit 124 | the `timeoutSeconds` value that forced the stop |
| `abandoned` | abandoned drain | `1`; the spill file may be partial |

The header is one line. The first byte of the output follows the
header's newline. When the output is empty, the header is the message.

The header omits `ms` when the record has no measured duration, so an
old record replays as `wisp:tool bash exit=1`.

### The system-prompt paragraph

Replace the current spill paragraph in `wisp_block` (445, near 458)
with:

```
Every tool result starts with one line of harness status, then the
command's output. The line begins "wisp:tool ". That line is not
output. Fields: name, exit, ms, and, only when they apply, bytes,
offset, rest_kb, spill, timeout_s, abandoned. exit is the process
exit code; nonzero is a fact, not a verdict (grep and diff use 1).
A result with spill="..." was truncated at the returned head. Read the
rest with: tail -c +<offset> <spill>. Set maxKilobytes=rest_kb on a
new call to read the rest in one piece. Spill files are never deleted.
The first byte after the status line is the command's first byte.
```

The paragraph is the durable guarantee. It survives a wording change
in the header, and it covers a command that prints a forged
`wisp:tool` line: the first line is the true one.

### Migration

An old record carries no `ms` and its `content` may end with the old
`Tool call notes` fence. A resumed session shows the new header above
the old fence for prior rounds. The old fence reads as output. New
sessions are clean. Do not rewrite `wisp.jsonl`.

## Touchpoints

- `Tools._execute_one` (2778): start a `Clock.monotonic()` clock after
  argument parsing; set `record["ms"]` before the end log; store
  `record["bytes"]`, `record["offset"]`, `record["rest_kb"]`,
  `record["spill"]`, `record["timeout_s"]`, and `record["abandoned"]`
  as the branches learn them.
- `Tools._run_tool` (2876): stop building prose. Fill the fields. The
  two-branch spill note collapses to one `rest_kb` number.
- Provider helper: one `tool_text_of(rec)` next to `message_of`
  (3432), called from the tool branches at 3455, 3512, and 3571.
  The helper builds the header and prepends the header plus a newline
  to `content`.
- `Renderer.tool_result` (4517): print `tool_text_of(payload)`, the
  same header and raw output the model receives, so the human view
  needs no translation; the dot line and the prose notes go.
- `records_to_stream` (4554): add `ms`, `bytes`, `offset`, `rest_kb`,
  `spill`, `timeout_s`, and `abandoned` to the replay payload.
- `wisp_block` (445, line 458) and the `render-live` help text (2097).

## Tests

One unit test with a fake clock that advances 2310 ms per call and a
fake executor that returns a chosen `(rc, head, spill, abandoned)`:

1. `record["ms"]` is 2310 and the end log line carries the same
   number.
2. Each of the three mappers starts the tool text with
   `wisp:tool bash exit=1 ms=2310\n`.
3. A call with `content == ""` and `exit == 1` yields a non-empty
   model-facing text.
4. Exit 0, empty output, no spill: the text carries `exit=0` and
   `bytes=0`.
5. A spill carries `bytes`, `offset`, `rest_kb`, and `spill`; the
   content after the first newline equals the raw head.
6. A 124 call carries `timeout_s=5` and no second explanation line.
7. `load_image` success and failure both carry a header.
8. A record with no `ms` renders `wisp:tool bash exit=1` and no
   duration.
9. Output that itself begins with `wisp:tool ...` leaves the true
   header first and the output verbatim after it.
10. Fresh and resumed serialization produce the same header bytes.
11. `render-past` shows the model-facing `wisp:tool` header line
    and the raw output, with no dot line and no prose note.

## Human render: the command echo sits in a code fence (2026-11-10)

The user rejected the bare command line joined to the `[bash 5s 5kb]`
tag: it is hard to find and hard to copy. The shipped shape keeps the
tag line, puts the command in a triple-backtick fence, and lets the
agent block follow the closing fence unchanged:

```
[bash 5s 5kb]
```
cat ./AI_SETUP_RECIPES.md
```
wisp:tool bash exit=0 ms=13 bytes=13818 offset=5001 rest_kb=9 spill="..."
# AI setup recipes
```

The fence replaces the V1 blank line as the boundary: it separates the
command from the tag line above and from the agent block below, it
gives a copy affordance in every terminal, and it costs two lines.
`Renderer.tool_header` (wisp/wisp) writes the fence when the payload
carries a command; a `load_image` call keeps the bare tag line because
its payload has no command. The agent block stays byte-identical:
`Renderer.tool_result` still prints `tool_text_of(payload)` verbatim,
the wire mappers and the two pinned goldens are untouched, and
`render-live` and `render-past` share the one path, so old sessions
replay with the fence. Check 11 of `tests/test_wisp_tool_status.py`
pins the fenced shape for a bash pair and the bare tag for
`load_image`.
