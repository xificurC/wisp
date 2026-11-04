# wisp

`wisp` is a minimal agentic LLM coding harness.

*Note:* No LLMs were used to write this readme.

## Goal

### Know exactly what you run

If you use `wisp` as-is, you get a tiny harness you understand. Nothing is hidden, everything is obvious.

### CLI friendly

Run headless, stream the output, compose commands through the shell.

### Extend, or run experiments

Due to its simplicity, it's trivial to run targeted experiments, or extend `wisp` exactly to your needs.

## Installation

Put `wisp` on your `PATH`, e.g. `ln -s $PWD/wisp/wisp ~/.local/bin/`.

## Example run

``` shell
# these can go in your .bashrc or project .env
export WISP_LLM_URL=https://my-llm.endpoint WISP_LLM_API_KEY=sk-apikey WISP_LLM_API=(anthropic | chat | responses)
# initialize a session - set model, thinking, system prompt
export WISP_SESSION_DIR=$(wisp new -m model -t high --env-in-system-prompt -s <(wisp build-system-prompt --skills --agents-md --wisp))
# run first query
wisp run <<<"tell me about nonviolent communication" | wisp render-live
# run followup query (same session, shared via `WISP_SESSION_DIR`)
wisp run <<<"give me 5 examples how to turn a jackal sentence to a giraffe one" | wisp render-live
```

## Architecture

`wisp` is a single-file python3 executable script, with no dependencies.

`wisp` has only 3 tools: `bash`, `python3` and `load_image`. `bash` and `python3` ship with a default 5 second timeout and 5 kilobytes output limit, making fast and small calls the default.

---

# Experiments

The following are extra tools included in this repository, which are experimental additions.

## `tikit`

A simple ticketing system. Tickets go to `<project-root>/.tickets/`. They have a YAML frontmatter, markdown body. That's it.

``` shell
tikit create --name "fix 42"
tikit query --json
```

## `wispy`

A wrapper around `wisp` and `tikit`. Added functionality:

- `tikit` creation and maintenance
- one-shot sessions. Every `wispy run` is a fresh LLM session, reading the ticket and state from the last `wispy run`.
- auto-compaction. `wispy run --context-guard 500k`, upon reaching the limit it forces a compaction and starts a new session.

### Example run

``` shell
# these can go in your .bashrc or project .env
export WISP_LLM_URL=https://my-llm.endpoint WISP_LLM_API_KEY=sk-apikey WISP_LLM_API=(anthropic | chat | responses)
export WISPY_TICKET=$(tikit create --name "fix 42")
wispy run <<<"build a plan" | wisp render-live
wispy run <<<"I approve the plan. Go." | wisp render-live
```

---

# Additional information

This readme gets you started. There's additional functionality in each tool that is not documented here. Rather than writing lengthy docs, you can read the source, which is short, or ask your agent to summarize the current implementation.
