---
id: 'wisp-o2llma'
name: 'running wisp with an opencode go subscription'
status: 'closed'
created: '2026-11-06T15:29:36Z'
parent: null
blocked-on: []
---

## Findings

OpenCode Go is a subscription, not a base URL alias. Its endpoint is
`https://opencode.ai/zen/go/v1`, one OpenAI chat-completions shape, and
`deepseek-v4.1-flash` is a listed model with a 1M context window and a
384k output cap.

The key in `OPENCODE_API_KEY` is a Go key. Three other routes refuse it:
`https://opencode.ai/zen/v1` answers `Insufficient account funds` on a
paid id and `FreeUsageLimitError` on a `-free` id, and the direct base
URL `https://opencode.ai/inference/openai/v1` answers `Insufficient
account funds`. Only the Go base URL bills the subscription
(`usage.opencode.billing_source` reads `go`).

OpenCode Go requires one header wisp did not send. Without
`x-opencode-session` the endpoint answers `MissingSessionID` and asks
for a stable id per conversation. The header is also the routing and
prompt-cache key.

OpenCode Go sits behind a Cloudflare blocklist on library user agents.
`Python-urllib/3.12`, wisp's default, answers `403 error code: 1010`;
`User-Agent: wisp` answers 200.

`/v1/model/info` answers 404 on the Go base URL, so `refresh_model_cfg`
writes nothing and warns on every run. `wisp.modelcfg` stays empty:
cost renders `<noprice>`, context renders `<nocontext>`, and a percent
context guard fails at start. A hand-written entry survives, because a
failed refresh writes nothing. Superseded 2026-11-06: wisp fetches no
model info; `WISP_LLM_MODEL_INFO_FILE` fills `wisp.modelcfg` (see
`## Model info and cache key`).

DeepSeek V4.1 Flash is gated by workspace privacy. The endpoint answers
`This Go model is hosted outside Europe and the United States. Select
Global at https://opencode.ai/console/<org>/settings/privacy#regions to
use it.` The setting is owner or admin work in the console; no local
change opens it. `glm-5.3-flash` runs on the same wiring without the
gate.

## Plan

Settled unit of work: make wisp speak to OpenCode Go, then document the
recipe.

1. Header env. Done. `extra_headers_of` parses `WISP_LLM_HEADERS` (one
   JSON object), fails on a non-object, and replaces `{session}` with
   the session dir's base name. `auth_headers_of` merges the extras
   last, so a provider with another auth scheme can replace the default
   header. The auth change later widened this overlay and removed the
   `refresh_model_cfg` HTTP call.
2. User agent. Done. `USER_AGENT = "wisp"`; `auth_headers_of` sends it,
   and `WISP_LLM_HEADERS` overrides it.
3. Docs. Done. `md/notes/opencode-go.md` holds the environment, the two
   refusals with their exact texts, the model list call, the
   `wisp.modelcfg` entry, the region gate, the free-tier distinction,
   and a verified run. `md/notes/providers.md` gains an "Extra headers"
   section that points at the note. The module docstring and the `wisp
   run` and `wisp continue` help env lines name `WISP_LLM_HEADERS`.
4. Tests. Done. `wisp/tests/test_providers.py` gains four cases: extras
   land with `{session}` substituted, extras win over the auth header,
   bad JSON exits 1, and the client names itself `wisp`.
5. Verify. Done. Every `tests/test_wisp_*.sh` passes, every
   `tests/*.py` script prints PASS, and `pytest wisp/tests tests -q`
   gives 148 passed. Live runs on the Go endpoint exit 0 for one text
   turn and for one tool round (`glm-5.3-flash`, `-t low`), and a
   hand-written modelcfg turns a `--context-guard 70%` run into `in 1.5k
   out 20 $0.000 524/1.0M 0.1%`. The same wiring renders through
   `wisp render-live` with `-t high`.

Evidence sessions: `wisp-sessions/oc-go-tools2` (tool round plus
modelcfg and guard), `wisp-sessions/oc-go-render` (render-live at `-t
high`), and `wisp-sessions/oc-go-smoke` (first text round).

## Out of scope

- Region gate: enabling Global for DeepSeek is console work by the
  workspace owner; wisp cannot open it.
- Prices from the endpoint: the Go usage body carries `cost` and
  `opencode.list_cost`, and wisp reads neither. Cost stays a
  `wisp.modelcfg` estimate.
- `/v1/model/info` absence: wisp adds no fallback that reads
  `/v1/models`, which does carry `limit.context` and per-million `cost`
  for Go. Resolution 2026-11-06: the caller's
  `WISP_LLM_MODEL_INFO_FILE`, filled by the recipe in
  `md/notes/providers.md`, carries those values into `wisp.modelcfg`
  without wisp fetching anything.

## Gaps

- DeepSeek V4.1 Flash needs the workspace privacy setting changed
  before a wisp run answers. Until then `glm-5.3-flash` is the verified
  stand-in on identical wiring.
- A `-t` level passes through as `reasoning_effort`. Go advertises
  `low`, `high`, `max` for DeepSeek V4.1 Flash. `medium` answered 200
  on `glm-5.3-flash`; DeepSeek stayed untested behind the region gate.
- Auth shape: settled by the user on 2026-11-06. One full-path URL,
  and `WISP_LLM_HEADERS` as the only auth override. No
  `WISP_LLM_PATH`, no `WISP_LLM_AUTH`. See `## Auth design, settled
  2026-11-06`.
- Model-info source: settled 2026-11-06 by
  `WISP_LLM_MODEL_INFO_FILE`; see `## Model info and cache key`.
- `prompt_cache_key`: settled 2026-11-06 and added to both OpenAI
  bodies; see `## Model info and cache key`.
- `AI_SETUP_RECIPES.md` has no inbound link from `README.md`;
  `md/notes/providers.md` points at the new doc alone. Options: add one
  line to the README "Example run" section, or leave the note pointer
  alone.
- Anthropic `-t` mapping: settled 2026-11-07 as option B, and done.
  `-t LEVEL` turns adaptive thinking on and rides
  `output_config.effort`; `WISP_LLM_THINKING_BUDGET` retires. See
  `## Anthropic thinking, option B, done 2026-11-07`.
- `AGENTS.md` sits in the staged set and this ticket does not own
  it: the file swaps the `<assistant-output-definition>` block for
  `<assistant-final-answer-definition>`. Options: keep the swap in the
  ticket commit, or unstage it with `git reset HEAD AGENTS.md` and
  commit the harness change on its own.

Settled since the list above: `WISP_LLM_ANTHROPIC_VERSION` retires and
`x-api-key` leaves the shape defaults (see the amendment); the
reasoning replay fix joins the plan; query redaction is approved, and
the bad-JSON message that echoes `WISP_LLM_HEADERS` redacts with it.

## Plan: auth change, opened 2026-11-06

Unit 1, URL. `WISP_LLM_URL` becomes the full request URL. `path_of`
retires. Start checks require an http or https scheme and a non-empty
path. `sse_stream` and `json_turn` change. `refresh_model_cfg` builds
no URL: `WISP_LLM_MODEL_INFO_FILE` replaces the fetch (settled later
the same day).

Unit 2, headers. `auth_headers_of` sends `Content-Type`, `User-Agent`,
and `Authorization: Bearer {key}` for all three shapes.
`WISP_LLM_ANTHROPIC_VERSION`, `x-api-key`, and `anthropic-version`
leave the code. `extra_headers_of` matches names case-insensitively,
deletes a header on a JSON `null`, and substitutes `{key}` beside
`{session}`.

Unit 3, key check. The mandatory-key check moves from `load_events` to
the resolved header table, so a no-auth local endpoint needs no key.

Unit 4, reasoning replay. Add the include to every `openai-responses`
body, set `reasoning.summary` to `auto` when thinking is set, replay
the stored summary text, and move the golden body pin.

Unit 5, redaction. `safe_log` redacts a query value whose name holds
key, token, or secret, and the bad-JSON message stops echoing the
header value verbatim.

Unit 6, docs and tests. Update `README.md`, `md/notes/providers.md`,
`md/notes/opencode-go.md`, the `run` and `continue` env lines, the four
`tests/test_wisp_*.sh` URL lines, and `wisp/tests/test_providers.py`.

## Model info and cache key, settled 2026-11-06

Two decisions from the user. Both close a gap.

1. `WISP_LLM_MODEL_URL` is dropped. `WISP_LLM_MODEL_INFO_FILE` names a
   JSON file keyed by model with the `wisp.modelcfg` shape: `context`
   plus per-million `input`, `output`, `cacheRead`, `cacheWrite`. Each
   run copies the file into `wisp.modelcfg`; how the caller fills the
   file is the caller's business. Unset means no copy and no warning,
   which also ends the OpenCode Go 404 warning. A missing, broken,
   empty, or non-numeric file warns and writes nothing, so a
   hand-written `wisp.modelcfg` survives. `md/notes/providers.md`
   carries a `jq` recipe per provider: OpenCode Go `/v1/models`
   (`limit.context`, per-million `cost`), OpenRouter (`context_length`,
   per-token `pricing`), and the LiteLLM price table. The OpenCode Go
   recipe ran live and wrote 30 entries. The LiteLLM recipe needs
   `del(.sample_spec)`, else wisp rejects the table; see `## Setup
   recipes, 2026-11-06`.
2. `prompt_cache_key` is added to the `openai-chat` and
   `openai-responses` bodies, set to the session dir's base name, the
   same id `x-opencode-session` carries. The field lands only when the
   session dir names a non-empty base, so a bare `build_request` in a
   test sends no empty key.

## Implementation record, 2026-11-06

Units 1-6 of the auth change are in `wisp/wisp`.

1. URL. `request_url_of` returns `WISP_LLM_URL` as written, checks the
   scheme and a non-empty path, and redacts a query secret in its
   error. `path_of` is gone. `sse_stream` and `json_turn` use the full
   URL; `refresh_model_cfg` builds no URL at all.
2. Headers. `auth_headers_of` sends `Content-Type`, `User-Agent: wisp`,
   and `Authorization: Bearer {key}` for all three shapes.
   `WISP_LLM_ANTHROPIC_VERSION` and every `x-api-key` default are gone.
   `extra_headers_of` keeps raw values: a JSON null deletes,
   `merged_headers` matches names case-insensitively, and `{session}`
   and `{key}` substitute after the merge.
3. Key check. `check_request_of` runs in `load_session_state`: full
   URL, known shape, resolved header table. The key check fails only
   when a surviving value holds `{key}` and the key is empty, so a
   no-auth endpoint needs no key. `load_events` checks nothing.
4. Reasoning replay. Every `openai-responses` body carries
   `include: ["reasoning.encrypted_content"]`, `reasoning.summary` is
   `auto` when thinking is set, and a reasoning item replays its
   `summary_text` beside the blob.
5. Redaction. `safe_log` sends every field through `redact_query_of`,
   which hides the value of a query pair whose name holds key, token,
   or secret. The bad-JSON `WISP_LLM_HEADERS` message names the parse
   position only, never the overlay value.
6. Docs and tests. `README.md`, `md/notes/providers.md`,
   `md/notes/opencode-go.md`, the `run` and `continue` help lines, four
   `tests/test_wisp_*.sh` URL lines, `wisp/tests/test_providers.py`,
   `wisp/tests/test_attachments.py`, and five harness URLs.

Verification: `python3 -m pytest wisp/tests tests -q` gives 165 passed.
`tests/test_wisp_nonstream_unit.py` and `tests/test_wisp_world_io_seam.py`
print PASS. The six shell suites pass: per_round_commit 4,
run_nonstream 5, stop_tool_call 1, sub_recipe 11, ls_grep 70,
registry 11. Live OpenCode Go runs exit 0 on `glm-5.3-flash` at
`-t low`: `wisp-sessions/oc-go-auth1` is one text turn with
`--context-guard 70%` and the model-info file, and
`wisp-sessions/oc-go-auth2` adds a tool round. The usage lines read
`478/1.0M` and `512/1.0M`, each with a price.
`WISP_LLM_URL=https://opencode.ai` fails at
start with "has no path". An empty key fails at start with
"WISP_LLM_API_KEY is not set" unless `{"Authorization":null}` removes
the header.

Migration: every stored `WISP_LLM_URL` needs its full path. This
machine's shell exports `WISP_LLM_URL=https://litellm.gratex.ai`, which
now fails the start check; the value must become
`https://litellm.gratex.ai/v1/chat/completions`.

## Setup recipes, 2026-11-06

`AI_SETUP_RECIPES.md` at the project root holds one copy-paste
environment block per backend: full URL, shape, key, extra headers, and
model-info file. Rows: OpenAI API key (chat and responses), OpenAI
subscription (Codex), Anthropic API key and subscription, OpenCode Go,
OpenRouter, Groq, Gemini OpenAI-compat, Azure OpenAI, LiteLLM proxy,
Ollama. OpenCode Go moves out of a provider-specific note into the one
table; `md/notes/opencode-go.md` stays the worked example.

One doc bug found and fixed. The LiteLLM recipe in
`md/notes/providers.md` wrote a table wisp refused: the public table
carries a `sample_spec` entry whose fields are English sentences, so
`model_table_ok_of` rejected the whole table and the run warned `not a
JSON object of model entries`, writing no `wisp.modelcfg`. The fixed
recipe starts with `del(.sample_spec)`, writes 3908 entries, and loads:
`-m gpt-5.1` with `--context-guard 70%` copies the file, passes the
guard, and leaves `gpt-5.1` in `wisp.modelcfg`.

Verification, both halves run live today. A stub endpoint recorded one
request per row: every row sends `Content-Type`, `User-Agent: wisp`,
`Authorization: Bearer {key}`, and its overlay; `{session}` became the
session dir's base name; `prompt_cache_key` carried the same name on
both OpenAI shapes; `{"api-key":"{key}","Authorization":null}` sent the
Azure key and no Bearer; the Azure `api-version` query landed as
written. Wrong-credential probes through wisp: OpenAI chat and
responses 401, Codex 401, Anthropic 401, OpenCode Go 401, OpenRouter
401, Groq 401, Gemini 400, local Ollama 404 model-not-found. Azure and
the LiteLLM proxy rows carry placeholder hosts and were not probed.

The Ollama block ran a real turn end-to-end on the local host: exit 0,
a one-line answer, and `in 611 out 23 $0.000 634/262k 0.2%` from
`wisp usage` with a hand-written two-entry file. `translategemma:4b`
answered 400 `does not support tools`, so the doc tells a caller to pick
a tool-capable model.

Model ids checked against the fetched tables: `gpt-5.1`,
`claude-sonnet-4-5` and `gemini-2.5-pro` exist bare in the LiteLLM
table; `glm-5.3-flash` and `deepseek-v4.1-flash` exist in the OpenCode
Go table; OpenRouter needs the `anthropic/claude-sonnet-4.5` spelling
and `openai/gpt-5.1`; Groq's `llama-3.3-70b-versatile` appears only as
`inferenceapis/llama-3.3-70b-versatile`, so the recipe tells the caller
to rename the key or add the entry by hand. Every backend block ends in
a `WISP_LLM_MODEL_INFO_FILE` line, so a copy-paste setup carries prices
and the context window.

## Auth sources, checked 2026-11-06

Five resources settle the headers a live probe cannot prove. Each claim
names the file that carries it.

Codex backend, `openai/codex` at `main`:

- `codex-rs/codex-api/src/requests/headers.rs` sends `session-id` and
  `thread-id` on every responses request, both with hyphens.
- `codex-rs/codex-api/src/endpoint/responses.rs` adds
  `x-client-request-id` and `Accept: text/event-stream`.
- `codex-rs/login/src/auth/default_client.rs` sets `originator` and
  `User-Agent` on every request from one shared client; the default
  originator is `codex_cli_rs`.
- `codex-rs/model-provider/src/bearer_auth_provider.rs` adds
  `Authorization: Bearer` and `chatgpt-account-id`, the lowercase form
  of the ticket's header.
- `codex-rs/core/src/client.rs` always sends
  `include: ["reasoning.encrypted_content"]`;
  `codex-rs/protocol/src/config_types.rs` defaults
  `reasoning.summary` to `Auto`.

litellm's `chatgpt/` provider mirrors the same route:

- `litellm/llms/chatgpt/common_utils.py` sends `Authorization`,
  `originator`, `user-agent`, `session_id`, and `ChatGPT-Account-Id`.
  The session header uses an underscore, unlike codex's hyphen. Apache
  and nginx drop underscore headers by default, so wisp follows codex
  and sends `session-id`.
- `litellm/llms/chatgpt/responses/transformation.py` mints a session
  id when none arrives (`uuid4` fallback), so a working client never
  omits the header.
- `openai/openai-python` carries no `chatgpt.com/backend-api` route,
  so `openai/codex` and litellm are the validated clients for this
  backend.

Anthropic, vendor docs and SDK:

- `platform.claude.com/docs/en/manage-claude/authentication` shows
  `Authorization: Bearer YOUR_API_KEY` as the current auth header and
  calls `x-api-key` the legacy alternative in its place.
- `platform.claude.com/docs/en/api/versioning` says every request must
  send `anthropic-version`, and gives `2026-10-21` as the example.
- `anthropic-sdk-python` at `main` sends `Authorization: Bearer` for an
  API key (`_api_key_auth`) and always sets `anthropic-version`
  (`ANTHROPIC_API_VERSION`) in its default headers.
- `litellm/llms/anthropic/common_utils.py` still sends `x-api-key` to
  `api.anthropic.com`, sends `Authorization: Bearer` when the key
  starts with `sk-ant-oat`, adds `anthropic-beta: oauth-2025-04-20`,
  and removes every `x-api-key` header in that case. The consumer
  OAuth path stays vendor-undocumented.

## Auth design, settled 2026-11-06

Two decisions from the user. Both supersede the auth shape above.

1. One URL. `WISP_LLM_URL` carries the full request URL: scheme, host,
   path, and query. wisp appends nothing. `path_of` retires, and
   `WISP_LLM_API` selects only the body and stream grammar. Start
   checks: scheme http or https, and a non-empty path; a bare origin
   fails with "WISP_LLM_URL has no path". This makes reachable the
   Codex route, `https://api.openai.com/v1/chat/completions` without a
   doubled segment, Gemini's `.../v1beta/openai/...`, Azure deployment
   paths, and LiteLLM prefixes. Cost: every stored config changes, four
   shell tests change, and the README examples change.

2. One auth mechanism. No `WISP_LLM_AUTH`. wisp keeps the per-shape
   default headers and completes the `WISP_LLM_HEADERS` overlay:
   names match case-insensitively; a JSON `null` deletes a header
   instead of sending `None`; `{key}` substitutes `WISP_LLM_API_KEY`
   beside `{session}`. The required-key check moves from `load_events`
   to the resolved table: a run fails only when a surviving value holds
   `{key}` and the key is empty. A no-auth local endpoint sets
   `{"Authorization":null}`, so a missing key then means exactly one
   thing.

### Amendment, 2026-11-06: no provider headers in code

Two more decisions from the user, both binding.

3. `WISP_LLM_ANTHROPIC_VERSION` retires. The variable existed only
   because the anthropic shape could not send a version header without
   pinning one, and wisp had no header overlay. The overlay carries
   `anthropic-version`, and the variable appears in no doc or help
   line. One header mechanism replaces it.
4. wisp pre-includes no `x-api-key` and no `anthropic-version`. Shape
   defaults stay `Content-Type`, `User-Agent`, and
   `Authorization: Bearer {key}` for all three shapes. The export list
   names every other header per backend. The vendor docs make Bearer
   correct for a native Anthropic API key, so the subscription row no
   longer needs a duplicated token or a deleted `x-api-key`.

Verified endpoints, one bogus-key POST each on 2026-11-06. Every URL
answered 401 or 400, so no row is a 404. Only OpenCode Go ran a full
turn; Ollama 0.24.0 answered on the local host. `WISP_LLM_API_KEY`
carries the key in every row.

| Backend | Full URL | Shape | `WISP_LLM_HEADERS` |
|---|---|---|---|
| OpenAI API key | `https://api.openai.com/v1/chat/completions` | `openai-chat` | - |
| OpenAI API key | `https://api.openai.com/v1/responses` | `openai-responses` | - |
| OpenAI subscription | `https://chatgpt.com/backend-api/codex/responses` | `openai-responses` | `{"ChatGPT-Account-Id":"<acct>","originator":"opencode","session-id":"{session}"}` |
| Anthropic API key | `https://api.anthropic.com/v1/messages` | `anthropic` | `{"anthropic-version":"2026-10-21"}` |
| Anthropic subscription | `https://api.anthropic.com/v1/messages` | `anthropic` | `{"anthropic-beta":"oauth-2025-04-20","anthropic-version":"2026-10-21"}` |
| OpenCode Go | `https://opencode.ai/zen/go/v1/chat/completions` | `openai-chat` | `{"x-opencode-session":"{session}"}` |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` | `openai-chat` | - |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | `openai-chat` | - |
| Gemini OpenAI-compat | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `openai-chat` | - |
| Azure OpenAI | `https://<res>.openai.azure.com/openai/deployments/<dep>/chat/completions?api-version=2024-10-21` | `openai-chat` | `{"api-key":"{key}","Authorization":null}` |
| LiteLLM proxy | `http://host:4000/v1/chat/completions` | `openai-chat` | - |
| Ollama | `http://localhost:11434/v1/chat/completions` | `openai-chat` | `{"Authorization":null}` |

A `-` row needs three exports: URL, shape, key. A row whose value is
not `-` adds the `WISP_LLM_HEADERS` object. The Codex row's body stays
unproven until a subscription access token runs a turn; wisp does not
obtain or refresh one. A legacy Anthropic deployment that wants the old
header sets `{"x-api-key":"{key}","Authorization":null,"anthropic-version":"2026-10-21"}`.

## Reasoning replay record

- `store:false` keeps no server-side item. A reasoning item crosses a
  turn only through its encrypted blob.
- The blob arrives only when the request's top-level `include` names
  `reasoning.encrypted_content`. Opencode's client sends
  `store:false`, `reasoningSummary:"auto"`, and that include for
  gpt-5-class models. Evidence: strings in `~/.opencode/bin/opencode`.
- Before the fix, wisp stored the blob and replayed it, and never
  asked for it; every replayed item was contentless.
- The prefix cache is not the break: the empty reasoning item is
  byte-stable, so the text prefix still hits. The loss is that prior
  reasoning never becomes input, so the model re-derives it as output
  tokens each round. Output tokens are never cacheable.
- Fix, approved and done 2026-11-06: add the include to the responses
  body for every `openai-responses` run; set `reasoning.summary:
  "auto"` when thinking is set; replay the stored summary text instead
  of `[]`. `## Implementation record` item 4 carries the result.
- Second source, `openai/codex`: `codex-rs/core/src/client.rs` sends
  the include unconditionally, and `codex-rs/protocol/src/config_types.rs`
  defaults the summary to `Auto`. Two independent clients agree.
- Unproven: the Codex backend body and its headers `originator`,
  `session-id`, `x-openai-internal-codex-residency`. The full URL makes
  the route reachable; a 200 needs a subscription access token.

## Auth scouting: OpenAI and Anthropic

Superseded on 2026-11-06: the vendor now documents
`Authorization: Bearer` for API keys, so `x-api-key` is not a
requirement; `WISP_LLM_HEADERS` plus the export list replaces the
version variable; and the auth change landed the full URL, the header
overlay, and the key check. The section stays as scouting history;
`## Auth design` and `## Implementation record` carry the current
truth.

Scope: OpenAI and Anthropic API keys and subscription tokens on
today's knobs, and the gap to a provider-independent auth flow.

Verified today:

- The endpoint is `WISP_LLM_URL.rstrip("/") + path_of(WISP_LLM_API)`,
  and `path_of` always starts with `/v1/`. A base that ends in `/v1`
  doubles the segment. No path override exists.
- Consequence: the Codex route
  `https://chatgpt.com/backend-api/codex/responses` is unreachable.
  wisp composes `.../codex/v1/responses`, which answers 404; the real
  route answers 401 without a token. Both probed live.
- An OpenAI API key on `https://api.openai.com` reaches the API for
  `openai-chat` and `openai-responses`: a bogus key returns
  `invalid_api_key`, so URL, path, and Bearer are right. No real key
  ran a full turn. The vendor-documented base `https://api.openai.com/v1`
  breaks the join.
- Anthropic requires `anthropic-version` on every request (docs:
  "you must send"). wisp sends the header only when
  `WISP_LLM_ANTHROPIC_VERSION` is exported. That variable appears in no
  doc, note, or help line, so an Anthropic API key fails out of the
  box.
- Anthropic answered the OAuth error, not the x-api-key error, when
  both headers arrived. A live probe with a bogus `sk-ant-oat01`
  token in both places said "OAuth access token is invalid"; with
  `x-api-key` only it said "invalid x-api-key". The old shape
  therefore forced a duplicated token and an undeletable `x-api-key`.
  The amendment ends that: no `x-api-key` is pre-included, so the
  subscription row needs only the beta and version headers.
- `WISP_LLM_HEADERS` turns a JSON `null` into the literal string
  `None`. It cannot delete a default header and cannot reference the
  key.
- README documents `WISP_LLM_API=(anthropic | chat | responses)`.
  wisp accepts only `openai-chat`, `openai-responses`, `anthropic`;
  `chat` and `responses` fail at start. The `run` and `continue`
  help lines omit `WISP_LLM_API` and
  `WISP_LLM_ANTHROPIC_VERSION`.
- `WISP_LLM_API_KEY` is mandatory, so a no-auth local endpoint
  (Ollama, llama.cpp) fails before the request.
- OpenCode's client sends the OpenAI subscription token to
  `https://chatgpt.com/backend-api/codex/responses` with
  `ChatGPT-Account-Id` when the token carries an account id. wisp
  can add the header today and cannot reach the path.

## Anthropic thinking levels, found 2026-11-06

`AI_SETUP_RECIPES.md` said "On the `anthropic` shape any `-t` value
turns thinking on". The sentence was true and incomplete.
`body_of_anthropic` tests truthiness only, so `-t low`, `-t high`, and
even `-t off` build one identical body:
`thinking: {"type": "enabled", "budget_tokens": <budget>}`. The level
word never reaches the wire and depth comes from
`WISP_LLM_THINKING_BUDGET` (8192, floored at 1024).

Three facts from `platform.claude.com/docs/en/api/messages`, read
2026-11-06:

- `output_config.effort` takes `low`, `medium`, `high`, `xhigh`,
  `max`. Anthropic carries a level field, so wisp drops a level word
  it could send.
- `thinking.budget_tokens` "Must be ≥1024 and less than `max_tokens`".
  wisp floors the budget and caps nothing: the two defaults (budget
  8192, max_tokens 4096) break that rule, so a plain `-t` run on this
  shape should answer 400. Unverified: no Anthropic key ran.
- `thinking.type` also takes `adaptive`, where "Claude decides when
  and how much to think", and `disabled`.

The finding waited on one decision until 2026-11-07. The user then
picked option B, and `## Anthropic thinking, option B, done 2026-11-07`
carries the current body, the file list, and the verification. The doc
sentence is rewritten in `AI_SETUP_RECIPES.md`.

## Anthropic thinking, option B, done 2026-11-07

The user picked option B. `body_of_anthropic` sets
`thinking: {"type": "adaptive"}` and `output_config: {"effort": <level>}`
when a thinking level is set, and sends neither key otherwise.
`DEFAULT_THINKING_BUDGET`, `ANTHROPIC_MIN_BUDGET`, and
`WISP_LLM_THINKING_BUDGET` are gone. The model picks the depth, so no
`budget_tokens` enters the body and the budget-below-max_tokens rule no
longer applies.

The vendor page `https://platform.claude.com/docs/en/api/messages.md`,
read 2026-11-07, carries both fields. `OutputConfig.effort` accepts
`low`, `medium`, `high`, `xhigh`, and `max`. `ThinkingConfigAdaptive`
takes `type: "adaptive"` plus an optional `display`. The page calls
`{"type": "enabled"}` manual extended thinking and keeps
`budget_tokens` for that mode alone.

Files changed:

- `wisp/wisp`: `body_of_anthropic` and its docstring; the two budget
  constants leave the constant block.
- `wisp/tests/test_providers.py`: `test_anthropic_body` asserts the new
  pair and the allowed top-level set; `test_env_overrides` keeps the
  `max_tokens` override; new `test_anthropic_thinking_level_rides_effort`
  walks all five vendor levels; new
  `test_anthropic_without_thinking_sends_no_thinking_keys` pins the
  silent default.
- `wisp/tests/smoke_paid.py`: the `WISP_LLM_THINKING_BUDGET` export is
  dropped; `WISP_LLM_MAX_TOKENS` stays.
- `AI_SETUP_RECIPES.md`: "Thinking and limits" names
  `output_config.effort` and its five words, drops the budget row, and
  the Anthropic API key recipe shows the body pair.

Verification: `python3 -m pytest wisp/tests -q` gives 167 passed. No
live Anthropic run ran: this machine holds no Anthropic key, and an
auth probe returns 401 before body validation.

Open: a level word outside the vendor list, `off` or `minimal` for
instance, passes through as written and fails at the endpoint, exactly
as the two OpenAI shapes behave.

## Settlement, 2026-11-07

Status set to closed at the user's request, for a commit of the working
tree. The work closed without a commit: the staged set waits on the
user. The one repair this session made to the tree is the trailing
space removed from `README.md` line 73, which leaves `git diff --check`
clean.

Delivered: the auth change (full URL, one header overlay, key check in
the resolved table), the reasoning replay, query redaction, the
model-info file, `prompt_cache_key`, the `wisp` user agent, the
Anthropic adaptive-thinking body, and the docs (`AI_SETUP_RECIPES.md`,
`md/notes/providers.md`, `md/notes/opencode-go.md`).

Verification at close, run on this tree: `python3 -m pytest
wisp/tests -q` gives 167 passed, and the six `tests/test_wisp_*.sh`
suites give per_round_commit 4, run_nonstream 5, stop_tool_call 1,
sub_recipe 11, ls_grep 70, registry 11. `git diff --check` is clean.

Residue, none of it blocking a commit:

- DeepSeek V4.1 Flash waits on the workspace region setting. No wisp
  change opens that gate.
- A `-t` level outside a vendor list passes through and fails at the
  endpoint, as both OpenAI shapes already behave.
- `AI_SETUP_RECIPES.md` has no inbound link from `README.md`. The
  choice between one README example line and the note pointer alone
  stays with the user.
