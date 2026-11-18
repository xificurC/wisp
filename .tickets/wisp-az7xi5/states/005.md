# Next
- Run the first real pass: `cd /home/pnagyux/code/wisp && bench/bin/harbor run -d terminal-bench@2.0 -a wisp_harbor:Wisp -m MODEL -e podman -l 20 -n 4 -k 1 -y -o bench/jobs/tb2-first`.
- Aggregate the pass: `python3 bench/aggregate.py bench/jobs/tb2-first`.
- Browse the pass: `bench/bin/harbor view bench/jobs/tb2-first/<timestamp> --jobs`.
- No env setup needed: `WISP_LLM_URL`, `WISP_LLM_API_KEY`, `WISP_LLM_MODEL_INFO_FILE` are already exported in the login shell.

# Open
- None.

# Cache
- The adapter now writes `<trial>/agent/trajectory.json` and fills `agent_result.cost_usd` plus the three token totals; `harbor view` reads job and trial table totals from `result.json` and per-step token metrics plus total cost from `trajectory.json`. (From: `bench/wisp_harbor.py`, `bench/jobs/smoke2/2026-11-18__14-55-05/*/result.json`, `bench/jobs/smoke2/2026-11-18__14-55-05/*/agent/trajectory.json`) (Serves: Next)
- Old jobs need `bench/.venv/bin/python bench/backfill.py JOBS_DIR`; the script writes the trajectory, rewrites each trial `agent_result`, and recomputes job totals. Verified on `bench/jobs/smoke`: 3,426 in / 191 out / $0.000156. (From: `bench/backfill.py`, backfill run output) (Serves: cold)
- `harbor view` hides token columns on the job page and trial table by default; the `Columns` control shows them and the choice persists in the URL. Tables print USD with two decimals, so sub-cent trials read `$0.00`; `aggregate.py` and the trial step list print four decimals. (From: viewer static JS, smoke2 viewer API, `bench/README.md`) (Serves: Next)
- `terminal-bench@2.0` is prefetched: all 89 tasks (49 MB) sit in `~/.cache/harbor/tasks`, so the first pass needs no dataset download. (From: `harbor download terminal-bench@2.0 --cache` output, ticket `## Setup`) (Serves: Next)
- `harbor view bench/jobs` fails with "Could not auto-detect folder type"; `harbor view bench/jobs/smoke --jobs` works. The `-o bench/jobs/NAME` option nests a timestamped job dir under NAME. (From: `harbor view bench/jobs` error, `harbor view bench/jobs/smoke --jobs` output) (Serves: Next)
- Dry-run without trials: append `--print-config` to any `bench/bin/harbor run` command. (From: `harbor run --help`, ticket `## Setup`) (Serves: cold)

# Pointers
- Ticket: /home/pnagyux/code/wisp/.tickets/wisp-az7xi5/ticket.md
- Repo: /home/pnagyux/code/wisp (session dirs: wisp-sessions/wisp-az7xi5-001 through -005)
- Bench home: /home/pnagyux/code/wisp/bench/ (wisp_harbor.py, backfill.py, aggregate.py, bin/harbor, install.sh, README.md; untracked; jobs/ and .venv/ gitignored)
- Harbor: /home/pnagyux/code/wisp/bench/.venv/bin/harbor (0.24.0); launcher: /home/pnagyux/code/wisp/bench/bin/harbor
- Smoke jobs: /home/pnagyux/code/wisp/bench/jobs/smoke (backfilled), /home/pnagyux/code/wisp/bench/jobs/smoke2 (fresh, native cost)
- Model table: /home/pnagyux/.config/wisp/gratex-litellm-models.json
- Registry index: https://raw.githubusercontent.com/laude-institute/harbor/main/registry.json
