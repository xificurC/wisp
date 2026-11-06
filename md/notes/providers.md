# Providers

wisp speaks to three request shapes. It has no vendor library. It builds
JSON, sends it with `urllib`, and reads the SSE stream.

## The URL

`WISP_LLM_URL` is the full request URL: scheme, host, path and query.
wisp appends nothing. A version path, a deployment prefix, and a query
string land as written, which is what Azure, Gemini's OpenAI-compatible
route, and a LiteLLM proxy need.

Start checks: the scheme must be `http` or `https`, and the path must
not be empty. A bare origin such as `https://my-llm.endpoint` fails
with `WISP_LLM_URL has no path`; write
`https://my-llm.endpoint/v1/chat/completions` instead.
`WISP_LLM_API` selects the body and stream grammar only.

## The three shapes

| Name | Example path | Auth header | System prompt |
|---|---|---|---|
| `openai-chat` | `/v1/chat/completions` | `Authorization: Bearer` | A message in the list |
| `openai-responses` | `/v1/responses` | `Authorization: Bearer` | A top-level `instructions` field |
| `anthropic` | `/v1/messages` | `Authorization: Bearer` | A top-level `system` field |

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
prices per million tokens. wisp fetches no model info. Point
`WISP_LLM_MODEL_INFO_FILE` at a JSON file with the same shape, and each
run copies the file into `wisp.modelcfg` before the first round.

``` shell
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/models.json
```

A missing, broken, or empty file warns and writes nothing, so a
hand-written `wisp.modelcfg` survives. Unset means no copy and no
warning. A model with no entry renders `<noprice>` and `<nocontext>`.
Only percent-mode guards need the window, and a missing window fails
that mode at start.

### Recipes

Every provider publishes model facts in its own shape. One `jq` call
turns the published list into the file wisp reads. Prices drift, so
treat each file as a snapshot.

OpenCode Go publishes `limit.context` and per-million `cost`:

``` shell
curl -s -H "Authorization: Bearer $OPENCODE_API_KEY" \
     -H "User-Agent: wisp" \
     https://opencode.ai/zen/go/v1/models \
  | jq 'reduce .data[] as $m ({};
        .[$m.id] = {
          context: ($m.limit.context // 0),
          input: ($m.cost.text.input.price // 0),
          output: ($m.cost.text.output.price // 0),
          cacheRead: ($m.cost.text.input.cache.read // 0),
          cacheWrite: ($m.cost.text.input.cache.write // 0)})' \
  > "$HOME/.config/wisp/models.json"
```

OpenRouter publishes `context_length` and per-token `pricing`:

``` shell
curl -s https://openrouter.ai/api/v1/models \
  | jq 'reduce .data[] as $m ({};
        .[$m.id] = {
          context: ($m.context_length // 0),
          input: (($m.pricing.prompt // "0") | tonumber) * 1000000,
          output: (($m.pricing.completion // "0") | tonumber) * 1000000,
          cacheRead: (($m.pricing.input_cache_read // "0") | tonumber) * 1000000,
          cacheWrite: (($m.pricing.input_cache_write // "0") | tonumber) * 1000000})' \
  > "$HOME/.config/wisp/models.json"
```

LiteLLM publishes one table keyed by model with its own key names:

``` shell
curl -s https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json \
  | jq 'del(.sample_spec)
        | with_entries(
          select(.value.input_cost_per_token != null)
          | .value = {
              context: (.value.max_input_tokens // 0),
              input: (.value.input_cost_per_token * 1000000),
              output: ((.value.output_cost_per_token // 0) * 1000000),
              cacheRead: ((.value.cache_read_input_token_cost // 0) * 1000000),
              cacheWrite: ((.value.cache_creation_input_token_cost // 0) * 1000000)})' \
  > "$HOME/.config/wisp/models.json"
```

`del(.sample_spec)` drops the table's one documentation entry, whose
fields are English sentences; wisp rejects a table whose entries are
not numbers. Each recipe rewrites the whole file, so give every backend
its own name when you use several.

Anthropic's `/v1/models` and OpenAI's `/v1/models` name no price. For
those, write the file by hand, or take the LiteLLM table above.
`AI_SETUP_RECIPES.md` at the project root holds one full environment
block per backend, the model-info file included.

## The paid smoke test

`wisp/tests/smoke_paid.py` is the only test that touches a real
endpoint. It is not in the suite, because it costs money and needs a
key.

It reads four variables from the environment:

| Variable | Holds |
|---|---|
| `WISP_LLM_URL` | The full request URL |
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

Put the model in the environment. Fill `wisp.modelcfg` from
`WISP_LLM_MODEL_INFO_FILE`, which is a caller snapshot of the
provider's list.

## Extra headers

`WISP_LLM_HEADERS` holds one JSON object of extra request headers and
lands last. Names match case-insensitively, so `authorization`
replaces `Authorization` instead of adding a second header. A JSON
`null` deletes a header: `{"Authorization": null}` reaches a no-auth
local endpoint. A value may carry `{session}`, the session dir's base
name, and `{key}`, `WISP_LLM_API_KEY`, so a backend with its own auth
header needs no duplicated export.

Every shape sends `Content-Type`, `User-Agent: wisp`, and
`Authorization: Bearer {key}`. wisp pre-includes no vendor header. A
native Anthropic endpoint therefore needs
`{"anthropic-version": "2026-10-21"}`, and a legacy deployment that
wants `x-api-key` sets
`{"x-api-key": "{key}", "Authorization": null}`.

The key check runs on the resolved table: a run fails only when a
surviving value still holds `{key}` and the key is empty, so a no-auth
endpoint needs no key.

wisp names itself in `User-Agent` (`wisp`), never the HTTP library: a
library name sits on a blocklist. `md/notes/opencode-go.md` is the
worked example.
