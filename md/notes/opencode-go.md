# OpenCode Go

OpenCode Go is a subscription that serves coding models behind one
OpenAI chat-completions endpoint. wisp reaches OpenCode Go with the
`openai-chat` shape and one extra request header.

## The environment

``` shell
export WISP_LLM_URL=https://opencode.ai/zen/go/v1/chat/completions
export WISP_LLM_API_KEY=$OPENCODE_API_KEY
export WISP_LLM_API=openai-chat
export WISP_LLM_HEADERS='{"x-opencode-session":"{session}"}'
```

`WISP_LLM_URL` holds the full request URL; wisp appends nothing, so
the `/v1/chat/completions` path is part of the export. A URL without a
path fails at start with `WISP_LLM_URL has no path`.
`WISP_LLM_HEADERS` holds one JSON object of extra headers. A value may
carry `{session}`, which wisp replaces with the session dir's base
name, so one exported variable gives every conversation its own stable
id.

## The session header

OpenCode Go refuses a request that carries no `x-opencode-session`:

```
{"type":"error","error":{"type":"MissingSessionID","message":"Request is
missing x-opencode-session and cannot be routed efficiently."}}
```

The header is the routing and prompt-cache key. `{session}` satisfies
the requirement without a per-session export.

## The user agent

OpenCode Go sits behind a blocklist that refuses a library user agent.
`Python-urllib/3.12` answers `403 error code: 1010`. wisp sends
`User-Agent: wisp`, and `WISP_LLM_HEADERS` overrides the value when a
caller wants its own name.

## The model list

Model ids are OpenCode Go's own names, not vendor names. Read the list
from the endpoint:

``` shell
curl -s -H "Authorization: Bearer $OPENCODE_API_KEY" \
  https://opencode.ai/zen/go/v1/models
```

`deepseek-v4.1-flash` is the DeepSeek V4.1 Flash entry, with a 1M
context window and 384k output tokens. `wisp new -m deepseek-v4.1-flash
-t high` selects it; `reasoning_effort` carries the thinking level.
Each entry also carries `limit.context` and per-million `cost`, which
the config recipe below reads.

## The model config

wisp fetches no model info, so build the table from the model list and
point `WISP_LLM_MODEL_INFO_FILE` at it:

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
export WISP_LLM_MODEL_INFO_FILE=$HOME/.config/wisp/opencode-go.json
```

Every run copies the file into `wisp.modelcfg` before the first round.
A percent context guard then works, and the usage line carries a price.
A hand-written `wisp.modelcfg` also survives, because a missing or
broken file writes nothing.

The `cost` object also carries time-of-day multipliers, and the recipe
reads the base price only. A subscription bills against an allowance,
not against these per-token prices; the file makes the figure a
list-price estimate. Token limits (`--context-guard 500k`) need no file
at all.

## The region gate

OpenCode Go blocks models hosted outside Europe and the United States
by default. DeepSeek V4.1 Flash is one of them:

```
This Go model is hosted outside Europe and the United States. Select
Global at https://opencode.ai/console/.../settings/privacy#regions
```

A workspace owner or admin selects Global under Settings › Privacy ›
Regions. An owner or admin can also enable the contributor models,
which train on request data.

## The free tier

The free model ids (`deepseek-v4.1-flash-free` and the other `-free`
names) belong to the OpenCode client, not to the Go API. A key answers
`FreeUsageLimitError` on a free id, and the direct pay-as-you-go base
URL `https://opencode.ai/inference/openai/v1` answers `Insufficient
account funds` without a balance. Go is the path for a subscription.

## A verified run

``` shell
export WISP_SESSIONS_ROOT=$PWD/wisp-sessions
DIR=$(wisp new -m glm-5.3-flash -t low)
wisp run -d "$DIR" <<<"Use the bash tool to print the current user name, then answer with that name only." \
  | wisp render-live
wisp response -d "$DIR"
wisp usage -d "$DIR"
```

The run exits 0, the tool round lands in `wisp.jsonl`, and the response
carries the printed name. The usage line reads `in 994 out 17
<noprice> <nocontext>` until `wisp.modelcfg` holds an entry, and a
loaded `WISP_LLM_MODEL_INFO_FILE` supplies that entry.
