# Next
- Analysis of benchmark round 2 is complete and recorded in ticket wisp-3s5m3t; the next step is the user's: `wispy commit`, another `wispy run`, or work in the parent ticket wisp-3v9vog.

# Open
- None (STOP; open questions live in ticket wisp-3s5m3t `## Gaps`).

# Cache
- Round-2 extraction recipe: `comparison.json` rows key `result_sha256` to transcript filenames `site/transcripts/<sha>.json.gz`; `report-metrics.json` uses the same keys. Fetch `origin/gh-pages`, then `git show origin/gh-pages:site/<file>` and gunzip into the analysis dir. Round-1 transcripts stay reachable at git ref `09f6e7e^` on gh-pages. (From: `~/code/curated-terminal-benchmark` git history, `site/comparison.json`, `site/transcripts.json`) (Serves: ticket `## Gaps`)
- The local clone `~/code/curated-terminal-benchmark` sits on branch `wisp-agent`; the new results live only on the remote-tracking ref `origin/gh-pages` (commit 09f6e7e replaced wisp's 12 transcripts; other agents' transcripts are untouched), and `origin/main` is one commit ahead of local `main`. (From: `git branch -a -v`, `git log origin/gh-pages`) (Serves: Next)
- Wisp round 2 ran harness version `e0d468f7` with the image, PATH, and S4 fixes; no failure among the six is harness-caused; remaining causes are behavioral and named in the ticket's "Cross-cutting causes, round 2". (From: site index.html head-facts, tr2 transcripts, verifier outputs) (Serves: Next)
- The wal regression diagnosis rests on diffing wisp's round-2 stage rewrites against the original stage sources visible in the round-2 transcript's event-4 `cat` output and against wisp's round-1 (passing) wal transcript recovered to `analysis/tr1/wal-recovery-ordering.json`. (From: `analysis/tr2/wal-recovery-ordering.json` events 4 and 7, `analysis/tr1/wal-recovery-ordering.json`) (Serves: ticket `## Gaps`)

# Pointers
- Ticket: `/home/pnagyux/code/wisp/.tickets/wisp-3s5m3t/ticket.md` (this session's analysis; parent: `/home/pnagyux/code/wisp/.tickets/wisp-3v9vog/ticket.md`).
- Analysis artifacts: `/home/pnagyux/code/wisp/wisp-sessions/wisp-3s5m3t-001/analysis/tr2/` (12 round-2 wisp transcripts, `view.py`, `view2.py`), `.../analysis/tr1/` (round-1 wal transcript).
- Benchmark repo: `~/code/curated-terminal-benchmark`, branch `wisp-agent`; data on `origin/gh-pages` under `site/` (`comparison.json`, `report-metrics.json`, `transcripts.json`, `transcripts/`).
