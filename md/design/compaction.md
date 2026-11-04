# Compaction

Compaction keeps the request base bounded. It replaces a finished
segment with one assistant record that holds the durable facts.

## The problem

Every record stays in the conversation. The model sees all of them on
every request. A long run grows its base without limit:

- Tool output is large and rarely needed twice.
- Reasoning blocks are large.
- The price per round rises with the base.

Compaction cuts the base. It must not lose a fact that later work needs.

## Two rules carry the design

### Rule 1: the kept record holds the facts, not the reasoning

Raw reasoning is reasoning about the past. It is not data. The model
can re-derive a plan; it cannot re-derive a file path that it read
earlier.

So the kept record holds text only. wisp drops every reasoning block
from the kept record before the commit.

The measurement that proved this:

| Measure | Value |
|---|---|
| Kept record 1, reasoning | 8,090 characters |
| Kept record 2, reasoning | 30,225 characters |
| First request of turn 3 | 15,482 prompt tokens |
| Share of that request from kept reasoning | about 63 percent |

Two thirds of the request was dead text. The backend also reported no
cache read, so the dead text billed at the full input price on every
round.

The archive keeps the full record, with reasoning. The strip is a view
change, not a deletion.

A load-time strip is forbidden. Records committed before the change
keep their bytes. A load-time strip would change a prefix that earlier
requests already sent, and the cache would miss.

### Rule 2: the scope is the segment, not the turn

The kept message must say what to keep. The early wording said "carry
the whole turn forward". With several segments in one turn, each kept
message re-copied the facts of the segments before it.

The measurement:

- Kept message 2 held 11,018 characters against 7,596 in message 1.
- The messages repeated their sections.
- The prompt floor rose from 4,804 tokens to 7,715 tokens after one
  compaction, a 60 percent rise.

The fix is the scope. A kept message holds the facts of its own
segment. The earlier kept messages still hold the earlier facts.

The segment start is a record. It is the last `continue` record, or the
user prompt of the turn when no `continue` record exists. The code and
the text use the same boundary.

## What compaction keeps

| Kind | Kept |
|---|---|
| File paths, ids, counts, decisions | Yes |
| Commands that worked, and their results | The result, not the output |
| Open questions and next steps | Yes |
| Raw reasoning | No |
| Full tool output | No, unless it is the result |

## The log line

The compact log line names what happened:

```text
compact round=N archive=M reasoning=K
```

`K` is the count of dropped reasoning characters. A reader can see the
size of the strip without reading the archive.

## What stays open

Compaction is a text policy. It cannot prove that a kept message holds
every fact. The standing rule in the notice tells the model to move
every durable fact from its thinking into the kept text. That rule is
the safety net. It is not a guarantee.
