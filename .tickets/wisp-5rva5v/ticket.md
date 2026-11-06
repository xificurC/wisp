---
id: 'wisp-5rva5v'
name: 'add wisp to curated-terminal-benchmark'
status: 'wip'
created: '2026-11-06T08:20:12Z'
parent: null
blocked-on: []
---

## Findings

The repository runs one Harbor agent class per harness from `src/ctb/agents/`; `src/ctb/matrix.py` registers each class, `ctb fetch` builds its archive, and `tests/` holds its unit tests. No wisp class exists.

wisp is a single-file standard-library script (`wisp/wisp` in `xificurC/wisp`). An install needs one archive unpacked into `/installed-agent` plus a PATH shim that runs the script under `/installed-agent/ctb-python/bin/python3`.

The repository reaches GPT only through the host `ctb.proxy`, which uses the ChatGPT subscription token. wisp streams every turn: `body_of_chat`, `body_of_responses`, and `body_of_anthropic` each set `stream: True`, and `sse_stream` reads only `data:` chunk lines, with no non-stream branch. `ctb.proxy` answers `stream: true` with HTTP 400 and a non-stream request with one JSON `chat.completion` body; wisp rejects that body as "an unexpected response". A provider switch does not avoid the proxy: `do_POST` routes only `/chat/completions` and `do_GET` only `/models`, so `/v1/responses` answers 404, and the upstream is the Codex backend with subscription headers, not api.openai.com. The 400 text "remove :stream from the features" is samizdat-era wording in `complete`. wisp could not run through the current proxy before `WISP_LLM_STREAM=false`; the switch now sends the one non-stream chat request the proxy answers. On its client side the proxy is a standard OpenAI chat-completions endpoint, non-stream only; `host_env` pops `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`, so the subscription token stays on the host. `_text` flattens message content parts and keeps only `text`, so the `image_url` parts `chat_image_message` builds arrive empty: `load_image` results never reach the model through the proxy.

The stated `wisp new --env-in-system-prompt -s <(wisp build-system-prompt --wisp)` form works under Harbor's `bash -c`. The concrete command adds `-m gpt-6.1-sol`, `-t medium`, `WISP_SESSIONS_ROOT=/logs/agent/wisp-sessions`, and `WISP_LLM_URL`/`WISP_LLM_API_KEY` from the proxy environment. A percent guard cannot run there: `context_guard_of` fetches `/v1/model/info` when the window is missing, and the proxy answers 404 for every path but `/models` and `/chat/completions`, so `--context-guard 70%` fails before round one; the token form `--context-guard 500k` needs no modelcfg.

The fork `xificurC/curated-terminal-benchmark` exists and SSH push works. The host has no `~/.vis/openai-codex-auth.json`, no dataset and no subscription token, so a live trial cannot run here.

Non-stream openai-chat differs by one key: `choices[0].message` replaces `delta`. Measured through wisp's own `TurnAcc`: the raw body yields no blocks, and a chunk-shaped re-wrap yields them only when tool calls are renumbered by position - a reply carries no tool-call `index`, so two calls collapse into one with concatenated arguments (reproduced). `finish_reason` and `usage` already land. Non-stream therefore took a new `WISP_LLM_STREAM=false` switch that sends `stream: false` and no `stream_options` in `body_of_chat`, a whole-body read beside `Http.post_stream` (it splits lines, so a pretty-printed body breaks it), and one chat reply adapter; the `openai-responses` (`output` items) and `anthropic` (`content` list) mappers stay out of scope. One synthesized `data:` chunk keeps `wisp.stream`, `render-live` and `render-past` unchanged; only incremental output is lost.

A direct Codex call is the same Responses body on another path (`backend-api/codex/responses`), plus `chatgpt-account-id` and `accept: text/event-stream` headers and four fields `body_of_responses` lacks: `parallel_tool_calls`, `prompt_cache_key`, `text.verbosity`, `reasoning.summary`. That route is the Codex CLI's private endpoint, not a documented public API, and serving it from the container needs the subscription token staged into the container. The route is stream-only upstream (`codex_body` forces `stream: True`), so `WISP_LLM_STREAM=false` does not serve it. wisp needs a full-URL env that wins over `path_of`, a header-map env, and a Codex body preset. Unverified: container egress to chatgpt.com, and whether the backend accepts a body without the cache-key and verbosity fields.

The benchmark repository is `/home/pnagyux/code/curated-terminal-benchmark`; its `origin` is `git@github.com:Blockether/curated-terminal-benchmark.git`. The wisp work branched from `origin/main` at `9edb0cc`, one commit ahead of the local `main`. A `fork` remote `git@github.com:xificurC/curated-terminal-benchmark.git` keeps `main` at `6075dbf`. `uv sync --frozen` works over the network, so the benchmark suite runs here: `uv run pytest -q` gives 286 passed, 2 skipped and one pre-existing failure, `tests/test_privacy.py::test_python_with_the_repository_on_its_path_turns_telemetry_off`. That test sets `PYTHONPATH` to the repository root while `sitecustomize.py` lives in `src/`, so the subprocess never sees it. The failure reproduces on untouched `main` and is out of scope.

The wisp arm needs no build: `ctb fetch` packs the one `wisp/wisp` file of commit `db3dfdf2` (`wisp-db3dfdf2.tar.gz`, 51 kB, mode 755) and setup unpacks it to `/installed-agent/wisp`. A PATH shim at `/installed-agent/wisp-bin/wisp` runs the script under the toolkit CPython, so a task image's interpreter never runs wisp. The proxy URL and key reach the container only through `secret_env`, as `WISP_LLM_URL` and `WISP_LLM_API_KEY`, so no command argument carries the key. `wisp new` writes `wisp.usage` as one plain usage object per turn, and `wisp usage` reports net input (prompt minus cache); the benchmark reports total input, as Dirge and Kmet do, so the arm sums `prompt_tokens` and keeps `cached_tokens` apart.

A local run of the exact command shape against `tests/fixtures/fake_llm_sse.py json_two`, which serves the same non-stream `chat.completion` wire, committed two tool records, printed the final answer, wrote two usage lines, and sent `stream: false`, no `stream_options`, `model: gpt-6.1-sol`, `reasoning_effort: medium` and three tools on both requests. wisp's `HTTP_TIMEOUT` is 600 s while `ctb.proxy`'s upstream timeout is 900 s, so wisp gives up first on a turn slower than ten minutes. `wisp.modelcfg` stays absent: the proxy answers 404 for `/v1/model/info`, and wisp warns once on stderr.

## Plan

Owner's choice: non-stream OpenAI chat completions through `ctb.proxy` only; the private Codex route is dropped. Every step is in `wisp/wisp` unless a path says otherwise.

1. Env switch. Add `stream_enabled_of(world) -> bool` beside `provider_of` (line ~2864): `WISP_LLM_STREAM` unset or empty means true; `false`, `0`, `no`, `off` (trimmed, case-insensitive) mean false; any other value fails naming the forms. `build_request` gains the gate: a false switch with `WISP_LLM_API` not `openai-chat` fails in one line, because the other two providers keep only their stream parsers.

2. Body gate. In `body_of_chat` (line 3381) send `"stream": False` and drop `stream_options` when `stream_enabled_of` is false; keep every other key in place, so the message prefix stays byte-stable. `body_of_responses` and `body_of_anthropic` stay as they are.

3. Whole-body read. Add `Http.post_json(url, headers, body, meta)` beside `post_stream` (line 2279): same request construction, HTTPError/URLError wrapping, and `meta` status/request-id fill; one `response.read()`, one `json.loads`, `HttpError("not a JSON response: ...")` on a parse failure. `post_stream` stays untouched; it splits lines, so a pretty-printed body would break it.

4. Reply adapter. Add `chat_chunk_of(payload)` beside `chunk_of` (line 3760): one chat-shaped chunk from one non-stream body, or None when the payload is not a dict or carries no `choices`. Map `choices[0].message.content` to `delta.content`; copy each `DEFAULT_THINK_FIELDS` key present on the message (the proxy sends none; a standard endpoint may send `reasoning_content`); map every `message.tool_calls` entry in order to `delta.tool_calls` with `index` set to its position, `id`, `type: "function"`, and `function.arguments` defaulted to `""`; carry `choices[0].finish_reason` and the top-level `usage`. The position index is required: `TurnAcc.apply_delta` merges by index, so unindexed calls collapse into one block with concatenated arguments (reproduced in Findings).

5. Turn dispatch. Add `json_turn(world, url, headers, body)` yielding the single chunk, with the same log lines: `http post url=... bytes=...` before the request; `http_error url=... ms=... status=... reqid=...` on a transport error; `http_done url=... mode=json payloads=1 ms=... status=... reqid=...` on success. An error object or a body with no choices fails with the existing "model endpoint returned ..." wording, through `stream_error_of`, `error_text_of` and `request_suffix_of`. Keep `sse_stream` intact and add `turn_stream(world, body)` as the single entry that `Llm.turn` calls; `stream_enabled_of` chooses `sse_stream` or `json_turn`. `json_turn` writes exactly one `data: <json>` line to stdout, so `wisp.stream`, `render-live`, `render-past` and `records_to_stream` need no change; only incremental output is lost. `TurnAcc`, the `wisp.usage` append, the token guard and the commit path already consume this chunk shape.

6. Docs. Add `WISP_LLM_STREAM` to the module docstring env list (line 62) and to the `wisp run` and `wisp continue` help env lines, with one sentence: false sends one non-stream chat request and prints the turn as one chunk.

7. Fixture. Extend `tests/fixtures/fake_llm_sse.py`: a `json` mode (one round: text plus usage) and a `json_two` mode (round one: two tool calls, round two: text plus usage), each answering `application/json` with a `chat.completion` body; when the request body says `stream: true`, answer 400 with the proxy's "stream is not supported" text, which pins the body gate; write each request body to `$FAKE_LLM_CAPTURE` when that env is set, so a test can inspect the wire body.

8. Tests. New `tests/test_wisp_run_nonstream.sh` on the `json_two` fixture with `WISP_LLM_STREAM=false`: exit 0; the capture shows `"stream": false` and no `stream_options`; both tool calls run as separate records with their own ids and arguments; `wisp.usage` carries prompt, cached and completion tokens; `wisp response` prints the final text; `wisp render-past` shows the answer. New `tests/test_wisp_nonstream_unit.py` on the `SourceFileLoader` pattern: `chat_chunk_of` maps content, two calls to index 0 and 1, finish_reason and usage; `TurnAcc` over that chunk yields three blocks (text, call, call), not two. Negative case: `WISP_LLM_STREAM=false` with `WISP_LLM_API=anthropic` fails with the one-line message.

9. Verify. Run every `tests/*.sh` and every `tests/*.py`. The proxy round trip is proven by the fixture's 400-on-stream and the captured body, not by a live proxy: the host has no subscription token, dataset or harbor package.

Status: steps 1-9 are done on branch `wisp-nonstream-chat` (commit `ebb61f0`), pushed to `xificurC/wisp`; every `tests/*.sh` and `tests/*.py` passes. The branch is ready for the PR and the PR stays unopened.

### Benchmark plan

Owner's later request: create the benchmark branch, do the changes, push the branch to the fork. Every step is in `curated-terminal-benchmark` unless a path says otherwise.

10. Agent class. `src/ctb/agents/wisp.py` pins `COMMIT = db3dfdf2...`, declares `ARCHIVE = artifacts/wisp-db3dfdf2.tar.gz`, and extends `CuratedAgent`. `install` adds the PATH shim; `secret_env` returns `WISP_LLM_URL` and `WISP_LLM_API_KEY`; `command` exports `PATH`, `WISP_SESSIONS_ROOT=/logs/agent/wisp-sessions` and `WISP_LLM_STREAM=false`, writes the instruction to `$HOME/problem.txt`, runs `wisp new --name wisp -m <model> -t medium --env-in-system-prompt -s <(wisp build-system-prompt --wisp)` into `$session`, and runs `wisp run -d "$session"` with stdout to `/logs/agent/wisp.stream`. No `--context-guard`. `populate_context_post_run` sums `wisp-sessions/wisp/wisp.usage` through `usage_totals` and records the turn count as metadata.

11. Matrix. `AgentSpec("wisp", "ctb.agents.wisp:Wisp", ("openai",), proxy=True)` right after samizdat, so wisp is a default arm and `ctb run` starts `ctb.proxy` for it.

12. Fetch and pins. `WISP_REPO` plus `fetch_wisp()` (`checkout` at `wisp.COMMIT`, `pack` the single script as `wisp`), appended to `fetch()`, and `pins()["wisp"] = wisp.COMMIT`.

13. Docs. README gains wisp in the agent list; the `fetch` docstring names it and says the script needs no build.

14. Tests. New `tests/test_wisp.py` with 7 tests: the proxy arm in the default matrix, the command (session flags, persona process substitution, no context guard, quoted instruction, no key), the proxy-only secrets and the missing-env failure, the usage sum over two turns plus a `data: ` line and a broken line, the missing usage file, the install upload and shim plus the missing-archive failure, and `fetch_wisp` with the pin and the no-rebuild second call.

15. Verify. `uv run ruff check src tests` and `uv run ruff format --check` pass; `uv run pytest -q` gives 286 passed, 2 skipped, 1 pre-existing failure. `fetch_wisp()` ran for real against the fork's GitHub repo and produced the 51 kB archive.

Status: steps 10-15 are done on branch `wisp-agent` (commit `2362a87`, base `origin/main` `9edb0cc`), pushed to `fork`. The PR stays unopened.


Out of scope for the wisp plan: the full-URL Codex route with its header-map env and body preset; non-stream mappers for `openai-responses` and `anthropic`; image parts (the proxy's `_text` drops them, so `load_image` stays inert); percent context guard (needs `/v1/model/info`). The benchmark agent class, matrix registration and `fetch_wisp` moved to the Benchmark plan and are done.

## Gaps

- Proxy streaming: settled by the owner - enrich wisp, not the benchmark, and take the one standard route only: non-stream chat completions through `ctb.proxy` under `WISP_LLM_STREAM=false`. The full-URL Codex route is dropped for this work: it is private, needs the subscription token inside the container, and is stream-only upstream.
- Benchmark side: settled - implemented as the Benchmark plan above (steps 10-15). Branch `wisp-agent` is pushed to `fork`; the PR opens from `https://github.com/Blockether/curated-terminal-benchmark/compare/main...xificurC:wisp-agent` and waits on the owner.
- Image tool: settled by the owner - accept the limitation. The proxy's `_text` drops image parts, so `load_image` stays inert under this benchmark, and wisp keeps advertising the tool.
- Effort and context guard: settled by the owner - `-t medium` with no `--context-guard`. Percent mode stays impossible through the proxy, and the token guard `500k` is not used.
- Invocation form: settled - the literal process substitution `-s <(wisp build-system-prompt --wisp)` is what the benchmark command uses; confirmed under `bash -c` and in the local end-to-end run.
- PR creation: settled for the wisp PR - the branch `wisp-nonstream-chat` is pushed over SSH and the PR opens from `https://github.com/xificurC/wisp/compare/main...wisp-nonstream-chat`; the `gh` keyring token stays invalid and is not needed. Opening waits on the owner.
- Live verification: unit tests only, or provision the Vis subscription token and the dataset for one trial. The Plan's step 9 assumes unit tests only; the Gaps still leave the choice open. The benchmark arm has never run in a container; the local end-to-end run used the wisp fixture, not `ctb.proxy`.
- Transcript reader: `src/ctb/report/transcripts.py` has no `read_wisp`, so `harness()` returns None for a wisp trial and the report shows only the task prompt, without a crash. Adding the reader is a separate unit of work.
- Turn timeout: wisp's `HTTP_TIMEOUT` is 600 s and `ctb.proxy` waits 900 s upstream, so a turn slower than ten minutes fails the trial inside wisp instead of the proxy.
- Pre-existing test failure: `tests/test_privacy.py::test_python_with_the_repository_on_its_path_turns_telemetry_off` fails on untouched `main` because it points `PYTHONPATH` at the repository root while `sitecustomize.py` sits in `src/`. Out of scope for the wisp branch.
