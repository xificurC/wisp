# AI setup recipes

One copy-paste environment block per backend. Each block carries the
full request URL, the request shape, the credential, the extra
headers, and the model-info file that holds prices and the context
window.

Checked in November 2026: wisp posted a request to every public URL
below with a wrong credential. Each endpoint answered 401 or 400, and a
local Ollama answered 404 model-not-found, so no path is wrong. The
Azure and LiteLLM rows carry placeholder hosts and cannot be probed.

`md/notes/providers.md` explains why wisp has three shapes and no
vendor library. `md/notes/opencode-go.md` is the OpenCode Go worked
example.

## What wisp reads

| Variable | Meaning | Default |
|---|---|---|
| `WISP_LLM_URL` | The full request URL: scheme, host, path, query. wisp appends nothing. | none, required |
| `WISP_LLM_API` | The body and stream grammar: `openai-chat`, `openai-responses`, `anthropic`. | `openai-chat` |
| `WISP_LLM_API_KEY` | The credential. Needed only while a request header still holds `{key}`. | empty |
| `WISP_LLM_HEADERS` | One JSON object of extra request headers. Names match case-insensitively. A JSON `null` deletes a header. A value may hold `{session}` and `{key}`. | none |
| `WISP_LLM_MODEL_INFO_FILE` | A JSON file keyed by model: `context` plus per-million `input`, `output`, `cacheRead`, `cacheWrite`. Each run copies the file into `wisp.modelcfg`. | none |
| `WISP_LLM_STREAM` | `false`, `0`, `no` or `off` sends one non-stream call. `openai-chat` only. | stream |
| `WISP_LLM_MAX_TURNS` | Round cap per run. | `99999` |
| `WISP_DEGENERATE_RETRY` | Textless attempts allowed before the run fails. | `3` |
| `WISP_SESSIONS_ROOT` | Where `wisp new` puts session dirs. | `<project root>/wisp-sessions` |

The model and the thinking level are not environment variables. They
live in the session dir: `wisp new -m MODEL -t LEVEL`. `wisp run` and
`wisp continue` take no `-m`, so the model stays with the transcript.

`wisp` sends three headers on every request: `Content-Type:
application/json`, `User-Agent: wisp`, and `Authorization: Bearer
{key}`. `WISP_LLM_HEADERS` lands last. wisp names itself, never the
HTTP library, because a library name sits on blocklists.

`{session}` and `prompt_cache_key` both carry the session dir's base
name. One conversation therefore keeps one route and one cache shard
on every backend that accepts an id.

## OpenAI API key, chat completions

``` shell
export WISP_LLM_URL=https://api.openai.com/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$OPENAI_API_KEY
# prices and window: LiteLLM table, recipe "litellm"; model id gpt-5.1
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m gpt-5.1 -t high
```

## OpenAI API key, Responses

``` shell
export WISP_LLM_URL=https://api.openai.com/v1/responses
export WISP_LLM_API=openai-responses
export WISP_LLM_API_KEY=$OPENAI_API_KEY
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m gpt-5.1 -t high
```

The Responses shape stores no server-side item: wisp asks for
`reasoning.encrypted_content`, keeps the encrypted blob, and replays
the summary text, so reasoning crosses the turn. `-t` lands as
`reasoning.effort` and turns `reasoning.summary` to `auto`.

## OpenAI subscription, Codex backend

``` shell
export WISP_LLM_URL=https://chatgpt.com/backend-api/codex/responses
export WISP_LLM_API=openai-responses
export WISP_LLM_API_KEY=$CHATGPT_ACCESS_TOKEN
export WISP_LLM_HEADERS=$(jq -cn --arg acct "$CHATGPT_ACCOUNT_ID" \
  '{"ChatGPT-Account-Id": $acct, "originator": "opencode",
    "session-id": "{session}"}')
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
```

wisp neither obtains nor refreshes a subscription token. This row is
probed to 401 only; a 200 needs a live chatgpt.com token.

## Anthropic API key

``` shell
export WISP_LLM_URL=https://api.anthropic.com/v1/messages
export WISP_LLM_API=anthropic
export WISP_LLM_API_KEY=$ANTHROPIC_API_KEY
export WISP_LLM_HEADERS='{"anthropic-version":"2026-10-21"}'
# prices and window: LiteLLM table, recipe "litellm"; model id claude-sonnet-4-5
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m claude-sonnet-4-5 -t high
```

wisp pre-includes no `anthropic-version` and no `x-api-key`. The vendor
now documents `Authorization: Bearer` for an API key, so the header
overlay carries the version alone. The `-t high` line above sends
`{"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}`.

## Anthropic subscription token

``` shell
export WISP_LLM_URL=https://api.anthropic.com/v1/messages
export WISP_LLM_API=anthropic
export WISP_LLM_API_KEY=$ANTHROPIC_OAUTH_TOKEN
export WISP_LLM_HEADERS='{"anthropic-beta":"oauth-2025-04-20","anthropic-version":"2026-10-21"}'
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
```

The consumer OAuth path stays vendor-undocumented. A legacy deployment
that insists on `x-api-key` sets
`{"x-api-key":"{key}","Authorization":null,"anthropic-version":"2026-10-21"}`.

## OpenCode Go

``` shell
export WISP_LLM_URL=https://opencode.ai/zen/go/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$OPENCODE_API_KEY
export WISP_LLM_HEADERS='{"x-opencode-session":"{session}"}'
# prices and window: OpenCode Go model list, recipe "opencode-go"
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/opencode-go.json
# wisp new -m glm-5.3-flash -t low
```

`x-opencode-session` is mandatory: the endpoint answers
`MissingSessionID` without the header, and uses the header as its
routing and prompt-cache key. `deepseek-v4.1-flash` needs the
workspace privacy setting set to Global in the OpenCode console;
`glm-5.3-flash` runs on the same wiring without the gate. OpenCode Go
bills an allowance, so the table prices are list-price estimates.

## OpenRouter

``` shell
export WISP_LLM_URL=https://openrouter.ai/api/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$OPENROUTER_API_KEY
# prices and window: OpenRouter model list, recipe "openrouter"
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/openrouter.json
```

## Groq

``` shell
export WISP_LLM_URL=https://api.groq.com/openai/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$GROQ_API_KEY
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m llama-3.3-70b-versatile
```

The LiteLLM table keys this model as
`inferenceapis/llama-3.3-70b-versatile`. Rename that key to the id Groq
accepts, or add the entry by hand: the `-m` value is the table key.

## Gemini, OpenAI-compatible route

``` shell
export WISP_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$GEMINI_API_KEY
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m gemini-2.5-pro
```

The LiteLLM table carries both `gemini-2.5-pro` and
`gemini/gemini-2.5-pro`. The first spelling matches the id the
endpoint accepts.

## Azure OpenAI

``` shell
export WISP_LLM_URL="https://$AZURE_RESOURCE.openai.azure.com/openai/deployments/$AZURE_DEPLOYMENT/chat/completions?api-version=2024-10-21"
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$AZURE_API_KEY
export WISP_LLM_HEADERS='{"api-key":"{key}","Authorization":null}'
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
```

Azure takes the key in `api-key` and the deployment in the path, so the
overlay supplies the real auth header and deletes the Bearer header.
Keep the `api-version` query in `WISP_LLM_URL`; wisp sends the query as
written.

## LiteLLM proxy

``` shell
export WISP_LLM_URL=http://host:4000/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_API_KEY=$LITELLM_KEY
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/litellm.json
# wisp new -m "$MODEL"          # a name the proxy lists in /v1/models
```

A proxy may rename a model, so add a model-info entry by hand when the
proxy name is not a LiteLLM table key.

## Ollama

``` shell
export WISP_LLM_URL=http://localhost:11434/v1/chat/completions
export WISP_LLM_API=openai-chat
export WISP_LLM_HEADERS='{"Authorization":null}'
# wisp new -m "$MODEL"          # a name `ollama list` prints
```

No credential, so the overlay deletes `Authorization`. A local model
needs no model-info file, so prices and a percent guard stay out of
reach. `--context-guard 64k` needs no window.

wisp sends the bash, python3 and load_image tools on every request, so
pick a model with tool support. Ollama answers 400 `does not support
tools` for a model without it. A model-info entry of zeros gives the
usage line a context window and a `$0.000` price; omit the entry and
only the placeholders show.

## The model-info file

`WISP_LLM_MODEL_INFO_FILE` holds one JSON object keyed by model. Each
run copies the file into `<session>/wisp.modelcfg` before the first
round. The copy costs one file read and no network call.

``` json
{
  "gpt-5.1": {"context": 272000, "input": 1.25, "output": 10,
              "cacheRead": 0.125, "cacheWrite": 0}
}
```

Prices are dollars per million tokens. The usage line prints a price
only when all four price fields exist, so write zeros instead of
omitting a field. A missing entry prints `<noprice>` and
`<nocontext>`. A missing, broken or empty file warns on stderr and
writes nothing, so a hand-written `wisp.modelcfg` survives. `~`
expands.

Keep one file per backend: each recipe rewrites the whole file. A
single `models.json` works for one backend at a time.

### Recipe: litellm, for OpenAI, Anthropic, Gemini, Azure and Groq

One public table with a key per provider, provider-prefixed and bare
spellings side by side.

``` shell
mkdir -p "$HOME/.config/wisp"
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
  > "$HOME/.config/wisp/litellm.json"
```

`del(.sample_spec)` matters: the table carries one documentation entry
whose fields are English sentences, and wisp rejects a table whose
entries are not numbers. The recipe wrote 3908 entries in November
2026.

### Recipe: openrouter

``` shell
mkdir -p "$HOME/.config/wisp"
curl -s https://openrouter.ai/api/v1/models \
  | jq 'reduce .data[] as $m ({};
        .[$m.id] = {
          context: ($m.context_length // 0),
          input: (($m.pricing.prompt // "0") | tonumber) * 1000000,
          output: (($m.pricing.completion // "0") | tonumber) * 1000000,
          cacheRead: (($m.pricing.input_cache_read // "0") | tonumber) * 1000000,
          cacheWrite: (($m.pricing.input_cache_write // "0") | tonumber) * 1000000})' \
  > "$HOME/.config/wisp/openrouter.json"
```

OpenRouter keys carry the vendor prefix, and so must `-m`:
`anthropic/claude-sonnet-4.5`, `openai/gpt-5.1`.

### Recipe: opencode-go

``` shell
mkdir -p "$HOME/.config/wisp"
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
  > "$HOME/.config/wisp/opencode-go.json"
```

### Check one model

The `-m` value and the table key must match byte for byte. A `missing`
answer means the file lacks that id.

``` shell
jq -r --arg m "$MODEL" '.[$m] // "missing"' "$HOME/.config/wisp/litellm.json"
```

## Thinking and limits

`-t LEVEL` lands as `reasoning_effort` on both OpenAI shapes, so the
backend decides the accepted levels. On the `anthropic` shape a level
turns adaptive thinking on: the body carries
`{"thinking": {"type": "adaptive"}}` and the level lands as
`output_config.effort`, whose accepted words are `low`, `medium`,
`high`, `xhigh`, and `max`.

| Variable | Meaning | Default |
|---|---|---|
| `WISP_LLM_MAX_TOKENS` | Anthropic `max_tokens` per turn. | `4096` |

Adaptive thinking gives Claude the depth choice, so wisp sends no
`budget_tokens` and reads no budget variable. The level word passes
through unchanged; a word the vendor does not list reaches the
endpoint and fails there.

## Checking the wiring

A wrong key must reach the endpoint and come back refused. A 404 means
a wrong path, and a local failure means a missing export.

``` shell
DIR=$(wisp new --name probe -m "$MODEL")
WISP_LLM_API_KEY=sk-wrong wisp run -d "$DIR" <<<"hi"
rm -rf "$DIR"
```

A pass reads `wisp: http error: 401 ...` or `400 ...`.

One real turn proves the credential and the price table:

``` shell
DIR=$(wisp new --name real -m "$MODEL" -t high)
wisp run -d "$DIR" <<<"say hello" | wisp render-live
wisp usage -d "$DIR"
```

The usage line reads `in 12 out 5 $0.000 40/272k 0.0%`. A `<noprice>`
or a `<nocontext>` names the missing model-info entry.

The env is read per run and never stored, so keep the exports in
`.bashrc` or a project `.env`. The model, the thinking level, and the
system record stay in the session dir.

`wisp run` binds a session dir through `-d DIR` or `WISP_SESSION_DIR`.
`wisp new` prints the session dir, so the one-line form is:

``` shell
export WISP_SESSION_DIR=$(wisp new -m "$MODEL" -t high)
```
