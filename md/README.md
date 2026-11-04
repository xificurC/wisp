# Design notes and specs

This directory holds the design knowledge of the three tools: `wisp`,
`wispy`, and `tikit`.

The notes are a distillation. They are not a history. They hold the
decisions, the reasons, and the measurements. They do not hold the
work log that produced them.

| Path | Holds |
|---|---|
| `specs/` | Three closed specs, carried as written. Each one argues one change. |
| `design/` | How each part works, and why it works that way. |
| `notes/` | Two smaller studies. Each one records a decision and its evidence. |

## Read order

1. `../README.md`: the tools and the quick start.
2. `design/session-model.md`: the core idea. Read this first.
3. `design/context-guard.md` and `design/compaction.md`: how a long
   run stays bounded.
4. `design/steering.md`: how to talk to a live run.
5. `design/skills.md`: how a system prompt is built.
6. `design/wispy.md` and `design/tikit.md`: the layer above `wisp`.
7. `design/testing.md`: how the code is tested.
8. `notes/`: the provider note and the shell study.

## A warning

Most numbers in these notes come from one machine and one model. Treat
them as orders of magnitude. Do not treat them as constants that hold on
your endpoint.

## Status

The specs are closed. They describe a change that already landed. Read
them for the reasoning. Do not read them as a task list.

The design notes stay open. Edit them when a decision changes.
