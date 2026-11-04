# Providers

wisp speaks to three request shapes. It has no vendor library. It builds
JSON, sends it with `urllib`, and reads the SSE stream.

## The three shapes

| Name | Endpoint | Auth header | System prompt |
|---|---|---|---|
| `openai-chat` | `/chat/completions` | `Authorization: Bearer` | A message in the list |
| `openai-responses` | `/responses` | `Authorization: Bearer` | A top-level `instructions` field |
| `anthropic` | `/messages` | `x-api-key` plus a version header | A top-level `system` field |

The shapes differ in more than the path:

| Difference | Effect on the code |
|---|---|
| Tool spec | Flat for the responses shape; nested under `function` for chat |
| Reasoning | A signed block for one, an encrypted item for another, a thinking block for the third |
| Stream events | Three event grammars, one internal event list |
| Stop reason | Three vocabularies, one internal word |
| Usage fields | Three names for cached tokens |

One adapter per shape does the mapping. The run loop sees one internal
record shape only.

## Why no vendor library

- The standard library is enough for a JSON POST and an SSE read.
- A library pins a version and drags a dependency tree.
- The wire shape is the contract. A thin adapter shows it.

The cost: wisp must track three grammars itself. The adapters are the
place for that work, and they are small.

## Cache accounting

A request has three token counts in practice:

| Count | Meaning |
|---|---|
| `prompt_tokens` | The whole request |
| `cached_tokens` | The part the backend served from its cache |
| `cache_write_tokens` | The part that entered the cache |

The net input is `prompt - cached - cache_write`. The figure is what
the run actually paid to process.

The three shapes report these under different names. One normalizer
maps them to one internal usage object. Every consumer reads that
object: the usage file, the renderer, the `usage` command, and the
smoke test.

A cache read is the only measure that proves the prefix is stable. A
test can assert the bytes; only the backend can assert the hit.

## The model config

`wisp.modelcfg` holds one entry per model: the context window and the
prices per million tokens. wisp fills it from one `/v1/model/info`
fetch, best effort.

A failed fetch warns and writes nothing. The run keeps going. A model
with no entry renders `<noprice>` and `<nocontext>`. Only percent-mode
guards need the window, and a missing window fails that mode at start.

## The paid smoke test

`wisp/tests/smoke_paid.py` is the only test that touches a real
endpoint. It is not in the suite, because it costs money and needs a
key.

It reads four variables from the environment:

| Variable | Holds |
|---|---|
| `WISP_LLM_URL` | The chat-completions base URL |
| `WISP_LLM_API_KEY` | The key |
| `WISP_SMOKE_MODEL` | The model id to call |
| `WISP_SMOKE_FALLBACK_MODEL` | A second model, tried when the first fails |

A per-provider override also works: `WISP_SMOKE_MODEL_ANTHROPIC`, and
so on.

The test runs four small turns: a prefix plant, a cache read, a tool
call, and a replay. It asserts a cache hit from turn 2, a tool block on
turn 3, and no signature failure on turn 4.

`--attach` swaps the run for one vision turn. A generated red PNG goes
inline, and the answer must name the color.

The test uses a small, cheap model. It does not prove a large model
works. It proves the wire path works.

## No model list, no prices

This note names no model and quotes no price. The endpoint changes, and
the prices change. A list in a README goes stale in a month.

Put the model in the environment. Read the price from `wisp.modelcfg`.
