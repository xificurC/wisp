# wisp bench

Benchmark the wisp single-file harness with Harbor over the company
LiteLLM endpoint. Adapter: `wisp_harbor.py` (agent `wisp_harbor:Wisp`).
Launcher: `bin/harbor` (no global install needed).

## Layout

    bench/
      wisp_harbor.py   Harbor agent adapter (wisp over LiteLLM)
      bin/harbor       launcher: sets PYTHONPATH, finds a harbor
      install.sh       fallback: venv at bench/.venv with harbor==0.24.0
      aggregate.py     pass-rate / token / cost summary over a jobs dir
      backfill.py      add cost/token fields to jobs run before the fix
      jobs/            run outputs (gitignored)

## Install

`bin/harbor` execs `bench/.venv/bin/harbor` if present, else the
curated-terminal-benchmark venv (harbor 0.24.0, already working). Only if
both are gone:

    bench/install.sh

## Environment

The adapter reads these from the harbor process environment (all already
set in the login shell):

    WISP_LLM_URL              LiteLLM chat-completions endpoint
    WISP_LLM_API_KEY          API key
    WISP_LLM_MODEL_INFO_FILE  price table, uploaded into the container
    WISP_BENCH_MODEL          model id, default for harbor -m (no default here)

Optional overrides: `WISP_BENCH_WISP_SRC`, `WISP_BENCH_CA_BUNDLE`,
`WISP_BENCH_MODELINFO`.

The adapter installs python3/git/ca-certificates in the task image,
uploads the host CA bundle, and sets `SSL_CERT_FILE`, because the task
images lack the company root CA the endpoint chains to.

## Dry-run (no trials executed)

Resolve the full job config for the first pass and print it, exit:

    bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp \
        -m "$WISP_BENCH_MODEL" -e podman -l 20 -n 4 -k 1 -y \
        -o bench/jobs/tb2-first --print-config

Prefetch the dataset (tasks only; images pull at run time):

    bench/bin/harbor download terminal-bench@2.0 --cache

Install the agent into one task container, then stop (no agent run, no
verifier):

    bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp \
        -m "$WISP_BENCH_MODEL" -e podman -l 1 -n 1 -y \
        -o bench/jobs/tb2-install --install-only

Smoke test (one trivial task, ~1 min, one trial):

    bench/bin/harbor run -d hello-world@1.0 -a wisp_harbor:Wisp \
        -m "$WISP_BENCH_MODEL" -e podman -n 1 -y -o bench/jobs/smoke

## Real runs

First pass: 20 of the 89 tasks, 1 attempt, 4 concurrent:

    bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp \
        -m "$WISP_BENCH_MODEL" -e podman -l 20 -n 4 -k 1 -y \
        -o bench/jobs/tb2-first

Full pass: all 89 tasks, 3 attempts for a pass-rate interval:

    bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp \
        -m "$WISP_BENCH_MODEL" -e podman -n 4 -k 3 -y \
        -o bench/jobs/tb2-full

Later tracks (see ticket wisp-az7xi5): `terminal-bench-pro@1.0` (200),
`aider-polyglot@1.0` (225), `swebench-verified@1.0` (500, one image build
per instance). Second model arm: pass a second `-m` value (repeatable
flag, one arm per model).

## Aggregate

    python3 bench/aggregate.py bench/jobs/tb2-first
    python3 bench/aggregate.py bench/jobs/tb2-first bench/jobs/tb2-full \
        --csv bench/jobs/summary.csv

Emits a summary table (trials, pass rate, mean reward, tokens, cost,
seconds) plus a per-task detail list. Cost comes from the per-turn
`cost` field LiteLLM reports, read out of the wisp session collected
into each trial directory.

## Backfill old jobs

A job run before the trajectory fix carries `cost_usd: null` and no
`agent/trajectory.json`, so `harbor view` shows no cost or steps. Convert
the collected wisp transcripts in place:

    bench/.venv/bin/python bench/backfill.py bench/jobs/smoke

The script writes `agent/trajectory.json`, updates each trial
`result.json` `agent_result`, and recomputes the job-level token and
cost totals. It is safe to re-run.

## Browse

    bench/bin/harbor view        # web UI over a jobs dir
    bench/bin/harbor trial ls -o bench/jobs/tb2-first

## Notes

- Harbor passes agent env through `docker compose exec -e`, so
  WISP_LLM_API_KEY lands in trial.log. Accepted for now (logs stay
  local); add a redactor before publishing any trial.log.
- Trial dirs keep the full wisp session under `agent/wisp-sessions/`,
  so `wisp render-past -d <trial>/agent/wisp-sessions/wisp` works on any
  finished trial.
- After the logs sync back, `populate_context_post_run()` converts
  `agent/wisp-sessions/wisp/wisp.jsonl` into `agent/trajectory.json`
  (ATIF) and copies the token and cost totals onto the Harbor
  `AgentContext`. This is what makes `harbor view` show the numbers:
  the job and trial tables read `agent_result` from `result.json`, and
  the trial page reads per-step token metrics and the total cost from
  `trajectory.json`.
- `harbor view` hides the token columns by default (both the job page
  and the trial table). Click `Columns` and enable `Uncached Input
  Tokens`, `Output Tokens`, and `Cached Input Tokens` once; the choice
  persists in the URL. Harbor prints USD with two decimals, so trials
  under one cent read `$0.00` in the tables even though the trial step
  list and `aggregate.py` print four decimals.
