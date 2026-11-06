# Next
- Confirm the staged set with `git status --short --branch` on branch `main` (79 files, nothing committed), then run `wispy commit`.
- Export the full URL before any wisp run: `export WISP_LLM_URL=https://company-litellm.example.com/v1/chat/completions`; the stored value has no path and fails the start check.
- When the workspace privacy setting reads Global, run one `DeepSeek V4.1 Flash` turn at `-t high` and read `wisp usage`.

# Open

# Cache
- HEAD was detached at the commit that `main` and `origin/main` both name, so `git checkout main` moved no content and the staged set sits on `main`. (From: `git rev-parse main origin/main HEAD`, `git branch --contains`) (Serves: Next)
- `tikit` at `/home/pnagyux/.local/bin/tikit` offers two commands, `create` and `query`; `query` prints one path per parseable ticket file, so `tikit query` with no error checks an edited frontmatter. `tikit ls` and `tikit show` do not exist. (From: `tikit --help`, `tikit query`) (Serves: Next)
- `.tickets/<id>/personas/` holds a one-line `.gitignore`, so `git add -A` leaves the persona files out of a commit while `.seq`, `.phase`, `STATE.md`, `responses/`, `states/`, `skills/` and `sessions.txt` go in. (From: `ls -la .tickets/wisp-o2llma`, staged name list) (Serves: cold)
- A base URL with a non-empty path passes the start check and 404s; only an origin with an empty or `/` path fails with "WISP_LLM_URL has no path". `https://opencode.ai/zen/go` passed the check and 404ed. (From: live run 2026-11-06, `wisp/wisp` `request_url_of`) (Serves: Next)
- `tests/test_wisp_nonstream_unit.py` and `tests/test_wisp_world_io_seam.py` assert at import and collect zero pytest cases; the 167 count comes from `wisp/tests` alone, and adding `tests` changes nothing. (From: `pytest wisp/tests -q`, 167 passed) (Serves: Next)
- The LiteLLM price table carries a `sample_spec` documentation entry whose fields are English sentences; `model_table_ok_of` rejects the whole table over that one entry, and `del(.sample_spec)` fixes the recipe; 3908 entries then load. (From: `md/notes/providers.md` recipe, `wisp/wisp` `model_table_ok_of`, live `jq` run) (Serves: cold)
- `wisp usage` prints a price only when the model entry holds all four of `input`, `output`, `cacheRead`, `cacheWrite`; a missing field prints `<noprice>` while the context window still renders. (From: `wisp/wisp` `usage_line`, live Ollama run) (Serves: cold)
- wisp sends the full bash/python3/load_image tool spec on every request, so a model without tool support fails at the endpoint: Ollama answered 400 "does not support tools" for `translategemma:4b`. (From: live run 2026-11-06, `wisp/wisp` `build_request`) (Serves: cold)
- The chat golden body literal lives in `wisp/tests/test_attachments.py` under `TestChatGoldenBody`, not in `test_providers.py`; `prompt_cache_key` moved that pin once. (From: `grep golden` across tests, `test_attachments.py:234`) (Serves: cold)

# Pointers
- Ticket: `.tickets/wisp-o2llma/ticket.md`, status `closed`; the closing record is `## Settlement, 2026-11-07`
- Branch `main`, 79 files staged, nothing committed. Verification: `python3 -m pytest wisp/tests -q` (167 passed) and the six `tests/test_wisp_*.sh` suites
- Anthropic body builder: `wisp/wisp` `body_of_anthropic` at line 3704; thinking branch at lines 3769-3772; `DEFAULT_MAX_TOKENS` 4096 at line 2959
- Anthropic tests: `wisp/tests/test_providers.py` lines 137 `test_anthropic_body`, 175 `test_env_overrides`, 182 `test_anthropic_thinking_level_rides_effort`, 190 `test_anthropic_without_thinking_sends_no_thinking_keys`
- Vendor doc: `https://platform.claude.com/docs/en/api/messages.md` (a `.md` suffix returns the page as markdown); local copy `/tmp/messages.md`
- New docs, both staged: `AI_SETUP_RECIPES.md` (363 lines) and `md/notes/opencode-go.md` (127 lines); `md/notes/providers.md` carries the "Extra headers" section
- Source: `wisp/wisp`; helpers `redact_query_of`, `check_request_of`, `session_key_of`, `request_url_of`, `extra_headers_of`, `merged_headers`, `auth_headers_of`, `model_table_ok_of`
- Recipe test output: `/tmp/aisetup/home/.config/wisp/litellm.json` (3908 entries), `openrouter.json` (458), `opencode-go.json` (30); stub harness `/tmp/aisetup/stub.py` and `/tmp/aisetup/drive.py`
- Evidence sessions: `wisp-sessions/oc-go-auth1` (text turn, percent guard, model file), `wisp-sessions/oc-go-auth2` (tool round); earlier `oc-go-smoke`, `oc-go-tools2`, `oc-go-render`
- Live model table: `/tmp/wisp-models/opencode-go.json`, 30 entries. Local Ollama: http://localhost:11434, 0.24.0; `translategemma:4b` (no tools), `qwen3.6:35b-a3b` (tools)
- No Anthropic key on this machine; an auth probe returns 401 before body validation
