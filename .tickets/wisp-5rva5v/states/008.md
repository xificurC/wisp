# Next
- Open the benchmark PR from the compare URL in Pointers only after the owner asks; branch `wisp-agent` is pushed to `fork`.
- Open the wisp PR from its compare URL only after the owner asks; branch `wisp-nonstream-chat` is pushed to `origin`.
- Get the owner's answers to ticket `## Gaps` before any live trial, transcript reader or turn-timeout work.
- After a wisp edit run `bash tests/<file>.sh` and `python3 tests/<file>.py`; after a benchmark edit run `cd /home/pnagyux/code/curated-terminal-benchmark && uv run pytest -q`.

# Open

# Cache
- The benchmark suite runs on this host: `uv sync --frozen` fetches into `.venv` (gitignored) and `uv run pytest -q` gives 286 passed, 2 skipped and one failure that also fails on untouched `main` (`tests/test_privacy.py` points `PYTHONPATH` at the repo root while `sitecustomize.py` is in `src/`). (From: `uv sync --frozen`, `uv run pytest -q`, the same test rerun after a stash) (Serves: Next)
- The wisp arm's wire was proven without the proxy: the exact command shape against `tests/fixtures/fake_llm_sse.py json_two` sent `stream: false`, no `stream_options`, `model: gpt-6.1-sol`, `reasoning_effort: medium` and three tools; two tool records committed; `wisp.usage` got one plain usage object per turn. (From: the fixture source, the local end-to-end run) (Serves: Next)
- The benchmark wisp arm lives in `src/ctb/agents/wisp.py` (pin `db3dfdf2`, archive `artifacts/wisp-db3dfdf2.tar.gz`, shim `/installed-agent/wisp-bin/wisp`), the matrix entry sets `proxy=True`, `cli.py` holds `fetch_wisp` and `pins()["wisp"]`, and `tests/test_wisp.py` holds 7 tests. (From: the files, `git show --stat` on the branch) (Serves: Next)
- wisp usage convention: `wisp usage` reports net input (prompt minus cache), the benchmark reports total input, so the arm sums `prompt_tokens` and keeps `cached_tokens` apart; `list_price` subtracts the cache. (From: `wisp/wisp` `read_usage_chunks`, `src/ctb/metrics.py` `list_price`) (Serves: Next)
- The wisp script path is `/home/pnagyux/code/wisp/wisp/wisp`: `/home/pnagyux/code/wisp/wisp` is a directory, so a shim that names it directly fails with "can't find '__main__' module". (From: the failed local run, `ls`) (Serves: Next)

# Pointers
- Ticket `/home/pnagyux/code/wisp/.tickets/wisp-5rva5v/ticket.md`; records are in `## Findings`, `## Plan` and `## Gaps`.
- wisp repo `/home/pnagyux/code/wisp`; script `wisp/wisp`; tests `tests/`; fixture `tests/fixtures/fake_llm_sse.py`.
- Benchmark repo `/home/pnagyux/code/curated-terminal-benchmark`; remotes `origin` = Blockether, `fork` = xificurC; commands `uv run pytest -q`, `uv run ruff check src tests`.
- wisp branch `wisp-nonstream-chat`; compare `https://github.com/xificurC/wisp/compare/main...wisp-nonstream-chat`.
- Benchmark branch `wisp-agent`; compare `https://github.com/Blockether/curated-terminal-benchmark/compare/main...xificurC:wisp-agent`.
- Commands: `bash tests/<file>.sh`; `python3 tests/<file>.py`; `wisp build-system-prompt --wisp`.
- Session dirs `wisp-sessions/wisp-5rva5v-002` through `-007` survey, plan and the wisp change; `-008` the benchmark arm.
