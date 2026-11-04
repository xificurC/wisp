# The context guard

The guard stops a run before the context window fills. The run stops
clean, the finished rounds stay committed, and the operator decides what
happens next.

## The rule

`--context-guard LIMIT` sets a limit. wisp checks the limit at each
round boundary. The check reads the `prompt_tokens` of the last
assistant record.

- A percent limit (`70%`) measures against the model's context window
  from `wisp.modelcfg`.
- A token limit (`150k`, `1m`, `200000`) is an absolute count.

When the count crosses the limit, the round boundary raises a guard
exit. wisp writes one stderr line, commits the finished rounds, and
exits 75.

## Why the check runs at a round boundary

A round boundary is the only safe point:

- the last round is committed;
- the record tail is stable;
- the next model request has not started.

A stop in the middle of a round would lose the round, or commit a
record with no tool results. Both break the resume rule.

## The check lags one round

The measure is the request that closed the last round. It is not the
request that the run would send next. So the check lags one round. The
lag is the price of a stable measure: the next request's size is not
known before the tools run.

A round that reports no usage skips the check. Some backends omit
usage. wisp does not guess.

## Why the check lives in the child

The first design put the check in a parent process. The parent polled
the child's usage file and stopped the child when the file grew past a
line.

The measurement killed that design:

- One run took 21 polls.
- The polls added 1.38 million prompt tokens.
- That was 47 percent of the session spend.

Each poll was a full request over the same context. The wrapper paid
more than the guard saved. The process boundary is not free.

So the check moved inside the run. It costs no request. It reads data
that the run already holds.

The rule that follows: put a guard where the measurement is already
available. Do not pay a second request to watch the first one.

## The stop is not a decision

wisp stops and reports. It does not compact, summarize, or restart on
its own. The stderr line names three next steps:

| Step | Command |
|---|---|
| Start a fresh session | `wisp new`, then `wisp run` |
| Add to the stopped session | `wisp run -d DIR < prompt` |
| Nothing | The session stays on disk. |

A wrapper can automate this. `wispy` does: it starts the next session
after a guard stop and carries the state forward (`wispy.md`).

## Percent mode needs a window

Percent mode needs a context window for the model. The window comes
from `wisp.modelcfg`, filled by one `/v1/model/info` fetch.

When the config holds no window, wisp tries one refresh. A run that
still has no window fails at start. It does not run blind.

The failure is loud on purpose. A silent fallback to a default window
would stop the run at the wrong place, or not at all.
