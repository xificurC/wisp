# The session model

One session is one directory. The directory is the whole state of the
run. A tool can read it, and a second tool can add to it, while the run
is live.

## The files in a session dir

| File | Holds |
|---|---|
| `wisp.jsonl` | The record of truth. One JSON record per line, in arrival order. |
| `wisp.run.json` | The setup: model, thinking level, and the list of child sessions. |
| `wisp.modelcfg` | The context window and the prices for each model seen. |
| `wisp.usage` | The usage chunks, one line each. |
| `wisp.log` | One line per internal event. |
| `wisp.stream` | The run stream, when a caller redirects it here. |
| `wisp.steer.inbox` | Queued steering messages. |
| `spill/` | Tool output that overflowed the size cap. Never deleted. |

`wisp.jsonl` is the record of truth. Every other file is a cache, a
log, or a channel. You can delete the rest. You cannot rebuild the
run without `wisp.jsonl`.

## Rounds

A round is one request to the model and the tool calls that the answer
holds. A round ends when the answer and its tool results are in hand.

wisp commits each completed round to `wisp.jsonl` as it ends. It does
not wait for the whole turn. A kill between two rounds loses at most
one round.

A record writes exactly once. The loop advances a write point after
each commit. The exit commit writes only the records that no round
wrote.

A commit needs a stable tail. wisp does not commit an assistant record
whose tool records are missing. A half-written round stays out until
the tools finish.

## Segments

A segment is the stretch of records since the last segment start. The
segment start is the last `continue` record. When no `continue` record
exists, the segment start is the user prompt of the turn.

The segment is the unit of compaction. It is not the turn. A turn can
hold several segments.

## The stream is not the record

`wisp run` streams the live turn to stdout as raw `data:` lines. Tool
calls and their results also enter the stream, as `data:` records. So a
renderer can follow the stream alone.

The stream is a view. The record is the file. A renderer that reads
`wisp.jsonl` sees the same events, after the fact.

`wisp render-live` reads the stream. `wisp render-past` reads the
record.

## Why the directory is the interface

The session dir is the only shared state. Nothing else is needed to
steer a run, to watch a run, or to resume a run:

- `wisp steer` writes a file.
- `wisp render-live` reads a stream.
- `wisp continue` reads the record and runs again.

This gives one rule for tools and tests. A tool that needs the run
needs the session dir path.

## The world

All IO goes through one `World` object. The world maps a name to a
constructor: the filesystem, the clock, the environment, the streams,
the LLM client, the session service, the prompt loader.

The code never calls `open`, `os.environ`, or `urllib` for business
logic. It asks the world. A test builds the same world with a different
registry and gets no real IO.

The rule is strict on purpose. The seam is the reason a test can replay
a recorded SSE stream with no network and no clock.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Done. |
| 1 | Error. One line on stderr names the cause. |
| 75 | The context guard stopped the run. The session stays resumable. |
| 124 | A tool call hit its timeout. |
| 130 | The operator pressed Ctrl-C. |
| 128+n | A signal killed the process. |

75 is reserved for the guard. No other wisp path exits 75. A caller can
tell a guard stop from a crash without a log parse.

## Resume

A run that stops keeps its file. Three commands continue it:

| Command | Does |
|---|---|
| `wisp run -d DIR < prompt` | Appends one user record and runs. |
| `wisp continue -d DIR` | Runs the loaded conversation, with no new user record. |
| `wisp steer -d DIR < message` | Queues a message for the next run. |

`continue` is for a kill or a turn limit. The killed segment's rounds
stay in the conversation as plain history.

## Session lineage

A child session names its parent with `--parent DIR`. `wisp new` writes
the child id into the parent's `wisp.run.json` children list. The link
goes both ways.

`wisp ls --tree` and `wisp grep --tree` walk the children list. A child
started without `--parent` is an orphan. The tree commands cannot see
it. Give the flag to every child.
