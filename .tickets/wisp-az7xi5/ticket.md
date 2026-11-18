---
id: 'wisp-az7xi5'
name: 'harbor-based terminal-bench harness and cost aggregation for wisp'
status: 'closed'
created: '2026-11-18T10:31:47Z'
parent: null
blocked-on: []
---

## Scout (2026-11-18)

### What wisp already measures

- Tokens: `<session>/wisp.usage` holds one JSON object per turn with
  `prompt_tokens`, `completion_tokens`, `cached_tokens`,
  `cache_write_tokens`, `reasoning_tokens`. `wisp usage -d DIR` folds the
  file into `in ... out ... $cost ... used/window`.
- Price: `wisp.modelcfg` is copied at run start from
  `WISP_LLM_MODEL_INFO_FILE`. `/home/pnagyux/.config/wisp/gratex-litellm-models.json`
  holds 31 models with `input`, `output`, `cacheRead`, `cacheWrite` per 1M
  tokens and a context window. The probe returned no `cost` field for
  `DeepSeek V4.1 Flash`, so the model table is the price source. The
  formula in `usage_line` is
  `net*input + cache*cacheRead + write*cacheWrite + out*output`, divided by
  1e6.
- Time: `wisp.log` carries epoch-ms on every event. `http_done ms=` is the
  LLM latency of one turn; `tool end ms=` is the tool latency. Wall-clock
  time must come from the runner.
- Pass/fail: wisp has no scorer. A task must ship hidden tests; the runner
  executes the tests after `wisp run`.
- Subagents: each child session has its own `wisp.usage`. The parent link in
  `wisp.run.json` and `wisp ls --tree` expose the tree. A team run must sum
  the whole tree, not the parent session alone.
- Turn cap: `WISP_LLM_MAX_TURNS` caps rounds. `wisp run --wallclock S` caps
  wall time (default 600 s).
- Session state: `wisp status -d DIR --json` returns tail, model, thinking,
  and usage totals.

### What wisp does not have

- No in-run compaction. `wisp run --context-guard LIMIT` stops at a round
  boundary with exit 75 and keeps the session resumable. `wisp continue`
  resumes the session.
- Compaction exists only in `wispy`: a work run with `--guard P` exits 75,
  a distill turn writes `STATE.md`, and the next session starts from the
  ticket plus `STATE.md`.
- No memory store beyond the transcript, project files, the AGENTS.md chain,
  skills, and wispy's `STATE.md`.
- No benchmark runner, task corpus, or scoring code in the repository.

### Local assets

- Company LiteLLM: the chat-completions endpoint named by `WISP_LLM_URL`.
  Models include `DeepSeek V4.1 Flash`, `GLM 5.3`, `Qwen 3.6 35B A3B`,
  `Qwen 3.8 27B`, `GPT 6.1 Sol`. `wisp -t` sends `reasoning_effort`.
- Sandbox: Docker 29.5.2 and Podman (runc) work.
- Toolchains on the host: Python 3, Node 24, Rust 1.95, Java 21, gcc,
  make, pytest. Go is absent.
- Prior local-endpoint runner: `experiments/tool-status/harness.py`
  (subprocess per run, repetitions, JSONL results, token/cost accounting).
- `~/code/curated-terminal-benchmark`: Harbor 0.24, a wisp agent arm over the
  GPT proxy, and 66 Terminal-Bench 4.0 tasks downloaded to
  `artifacts/datasets` (505 MB). The wisp arm accepts only `GPT 6.1 Sol` and
  needs a local-endpoint variant.
- Prior wisp results: tickets `wisp-3v9vog` and `wisp-3s5m3t` analyze 12
  Terminal-Bench tasks against five harnesses.

No benchmark code was written in the scout session; the scout record and
the options were its deliverable.

## Probe (2026-11-18)

Goal: find a ready dataset plus a harness that needs near-zero code.

- Harbor 0.24 is installed at `~/code/curated-terminal-benchmark/.venv/bin/harbor`.
  `harbor run -d NAME@VERSION` pulls a dataset by name; `harbor download` writes it to disk.
  The registry index is `https://raw.githubusercontent.com/laude-institute/harbor/main/registry.json`
  and lists 80 datasets.
- Dataset sizes: termigen-environments 3566, vmax-tasks 1043, swe-gen-js 1000,
  swebenchpro 731, swebench-verified 500, dabstep 450, swebench_multilingual 300,
  aider-polyglot 225, terminal-bench-pro 200, featurebench 200, terminal-bench 2.0 89,
  openthoughts-tblite 100, quixbugs 80. Local copy of terminal-bench 4.0 has 66 tasks.
- Terminal-Bench 2.0 and Pro use prebuilt ghcr images. The SWE-bench family builds one
  image per instance (build timeout 1800 s, 1 CPU, 4 GB).
- A 93-line Harbor agent (now `bench/wisp_harbor.py`) runs wisp over LiteLLM.
  Two podman runs passed:
  - `hello-world@1.0`: reward 1.0, 1 turn, 1834 in / 24 out, 64 s including the image build.
  - `terminal-bench-sample/log-summary-date-ranges`: reward 1.0, 5 turns, 10 bash calls,
    134 s of agent time, 31,733 in / 1,996 out, about $0.0016 at the model table price.
    Model latency was 66 s of the 134 s; tool time was under 1 s.
- Container prerequisites, found by trial: python3, git, and the company CA bundle. The
  endpoint certificate chains to `CA-GTICA2K8`, which the image's public bundle lacks;
  `SSL_CERT_FILE` fixes the failure.
- wisp bug: `git_root` calls git unguarded. A container without git makes `wisp new` exit 1
  with `kind=internal` and a traceback only in `wisp.log`.
- Harbor passes agent env through `docker compose exec -e`, so the API key lands in
  `trial.log`. The curated repo has `ctb.privacy` for this; the probe agent has no redactor.
- LiteLLM returns a per-turn `cost` field here, so cost needs no price table.

Probe conclusion: Harbor plus the registry datasets needs one agent file, no new framework
and no task authoring. Terminal-Bench 2.0 and Pro fit wisp's shell tools and need no image
build. Aider-polyglot is the cheap high-volume track. The SWE-bench family is the
repo-scale track and pays one image build per instance.

## Options

- A. Bespoke light harness with authored mini-repos: rejected. Task authoring
  and calibration were the whole cost, and the registry measures the same
  thing with real tasks.
- B. Terminal-Bench through Harbor: chosen, widened to any registry dataset.
  The probe removed the GPT/proxy plumbing cost; one local-endpoint agent file
  replaces it.
- C. Public small-task suite: kept, not ported. `aider-polyglot@1.0` and
  `quixbugs@1.0` run through Harbor with no porting work.
- D. Inspect AI: rejected. Harbor supplies logs, scorers, parallelism and the
  datasets already.

## Recommendation

Take Harbor plus the registry datasets. Run Terminal-Bench 2.0 (89 tasks),
then Terminal-Bench Pro (200), then Aider polyglot (225) for cheap volume.
Add `swebench-verified@1.0` (500) only for repo-scale debugging, because each
instance builds an image.

The adapter lives at `bench/wisp_harbor.py`, hardened (see Setup); the
redactor was dropped because the logs stay local.

```
bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp \
  -m MODEL -e podman -l 20 -n 4 -k 1 -y -o bench/jobs/tb2-first
```

Harbor supplies one `result.json` per trial; `bench/aggregate.py` is the
cross-trial aggregate.

## Setup (2026-11-18)

`bench/` at the repo root is the benchmark home; it replaces
`experiments/bench/` (file moved, old dir removed).

- `wisp_harbor.py`: the adapter, hardened. install() installs
  python3/git/ca-certificates in the task image and uploads the host CA
  bundle plus the model price table; run() sets `SSL_CERT_FILE` and
  `WISP_LLM_MODEL_INFO_FILE` only when the table was uploaded. Host paths
  overridable via `WISP_BENCH_WISP_SRC`, `WISP_BENCH_CA_BUNDLE`,
  `WISP_BENCH_MODELINFO`. No redactor: logs stay local.
- `bin/harbor`: launcher shim. Puts bench/ on PYTHONPATH so
  `-a wisp_harbor:Wisp` resolves without a manual export, then execs
  `bench/.venv/bin/harbor` if installed, else the
  curated-terminal-benchmark venv (harbor 0.24.0). Fixes "harbor not on
  PATH" with no global install.
- `install.sh`: fallback installer for a self-contained `bench/.venv`
  with harbor==0.24.0. Fixed 2026-11-18: `BENCH_DIR` carried a wrong
  `/..` (copied from `bin/harbor`, which sits one level deeper), so the
  script built `/home/pnagyux/code/wisp/.venv` and called
  `<repo>/bin/harbor`, which does not exist. Line 6 now resolves to
  `bench/` itself. The stray repo-root `.venv` from the failed run was
  removed. `install.sh` then ran clean: `bench/.venv` built, harbor
  0.24.0 installed, shim prefers `bench/.venv`, and the first-pass
  dry-run (`--print-config`) resolves under the new venv.
- `aggregate.py`: aggregation over a jobs dir. Summary table (trials,
  pass, error, pass rate, mean reward, in/cache/out tokens, cost,
  seconds) plus per-task rows. Cost is the per-turn `cost` LiteLLM
  reports, read from the wisp session Harbor collects into each trial
  dir. Verified against the smoke jobs: reproduces the probe numbers
  (logsum 31,733 in / 1,996 out / $0.0016 / 134 s; smoke4 1,834 / 24 /
  64 s).
- `README.md`: install, environment, dry-run, real-run, aggregate, and
  browse commands.
- `.gitignore`: jobs/, .venv/.

Validated without running trials: the shim prints harbor 0.24.0; the
adapter imports under the harbor venv; `harbor run --print-config`
resolves the first-pass job (terminal-bench@2.0, 20 tasks,
wisp_harbor:Wisp, DeepSeek V4.1 Flash, podman) and exits;
`harbor download terminal-bench@2.0 --cache` fetched all 89 tasks
(49 MB) into `~/.cache/harbor/tasks`.

## Decisions (2026-11-18)

1. Dataset: `terminal-bench@2.0`. First pass capped `-l 20`; full pass
   all 89 tasks.
2. Repetitions: `-k 1` for the first pass; `-k 3` for the full pass.
3. Adapter hardening: done in `bench/wisp_harbor.py` (git, python3, CA
   bundle). Redactor dropped; logs stay local.
4. wisp git bug: left as is. The adapter installs git in the task image,
   so the benchmark never hits the unguarded `git_root`.
5. Aggregation: `bench/aggregate.py` over the jobs dir; `harbor view`
   for browsing.
6. Compaction and memory track: skipped this round; no registry dataset
   covers either.
7. Model set: `DeepSeek V4.1 Flash` only for the first passes; add
   `GLM 5.3` as a second arm after the first full pass.

## View metrics (2026-11-18)

Problem: `harbor view` showed no cost and no token consumption for a wisp
trial. Cause: the adapter set token totals in `run()`, but Harbor calls
`populate_context_post_run()` only when the `AgentContext` is still empty, so
the post-run step never ran. `result.json` carried `cost_usd: null`, and no
`trajectory.json` existed, so the trial page had no cost, no steps, and no
per-step token metrics.

Fix in `bench/wisp_harbor.py`:
- Moved context population to `populate_context_post_run()`, which Harbor
  calls after the agent logs sync back to the host.
- Added `convert_trajectory()`: reads
  `agent/wisp-sessions/wisp/wisp.jsonl`, builds ATIF steps (user, agent,
  tool observations), and writes `agent/trajectory.json` with per-step
  `prompt_tokens`, `completion_tokens`, `cached_tokens`, `cost_usd`, plus
  `final_metrics` totals.
- Copied `final_metrics` onto the `AgentContext` (`cost_usd` and the three
  token counts). Harbor backfills `model_usage` from `trajectory.json`.
- Kept the in-container `wisp.usage` scrape as a fallback for a missing
  transcript; the fallback now also sums the per-turn `cost`.
- `bench/backfill.py`: converts transcripts for jobs run before the fix,
  writes `agent/trajectory.json`, rewrites each trial `result.json`
  `agent_result`, and recomputes job-level token and cost totals. Safe to
  re-run.

Verified:
- `hello-world@1.0` at `bench/jobs/smoke2/2026-11-18__14-55-05`:
  `result.json` has `cost_usd 9.71e-05`, 3,430 in / 83 out;
  `agent/trajectory.json` has 3 steps and matching `final_metrics`; the
  viewer API returns `total_cost_usd 9.71e-05` and the per-step metrics.
- Backfilled `bench/jobs/smoke`: the trial reads 3,426 in / 191 out /
  $0.000156 (was 1,754 / 135 / null); the viewer API returns the new totals
  and a 3-step trajectory.

Reading `wisp.jsonl` is authoritative; the old in-run `wisp.usage` scrape
undercounted that smoke trial. Remaining display facts, not data gaps:
Harbor hides the token columns on the job page and trial table by default
(the `Columns` control enables them), and the tables print USD with two
decimals, so sub-cent trials read `$0.00` there. `aggregate.py` and the
trial step list print four decimals.
