---
id: 'wisp-elak2h'
name: 'clean commits of internal references'
status: 'closed'
created: '2026-11-10T11:02:39Z'
parent: null
blocked-on: []
---

## Goal

Scrub LLM internals (API key, URL, model alias) from commits, per the new
`<git-commit-rules>` block in `AGENTS.md`. Amend unpushed commits; report
leaks already in pushed commits.

## Amended (unpushed)

Rebuilt `wip(ai-wpueub): wispies` (was `7a7d3d5`, now `a8797fe`) and
replayed the three commits above it. Only `.tickets/ai-wpueub/` changed:

- The internal company gateway URL became the phrase "Company LiteLLM
  server" in `STATE.md`, `states/001.md`, and `states/002.md`.
- Six model aliases became generic display names in `design-options.md`,
  `design-options-v1.md`, and `responses/001.md`.

Verification: every file added or changed in `origin/main..main` scans
clean for the company gateway host, the model slugs, and real keys.
`git diff 9d31ba6 HEAD` lists only the six `.tickets/ai-wpueub/` files.
No commit message leaked. No push happened at that turn; `main` was five
commits ahead of `origin/main`.

## Pushed leaks (report at that turn; superseded below)

These sit in pushed commits, so amending them would rewrite published
history. Listed for the owner's decision. This report names file
paths only; it does not reproduce the leaked values.

### Internal company gateway URL

Introduced by pushed commit `e0d468f` (`origin/main` tip).

- `.tickets/wisp-o2llma/STATE.md:3`
- `.tickets/wisp-o2llma/responses/005.md:38`
- `.tickets/wisp-o2llma/states/005.md:2`
- `.tickets/wisp-o2llma/states/006.md:2`
- `.tickets/wisp-o2llma/states/007.md:3`
- `.tickets/wisp-o2llma/states/008.md:2`
- `.tickets/wisp-o2llma/states/009.md:3`
- `.tickets/wisp-o2llma/ticket.md:231,233`

### Used model alias

- `wispy/wispy:74` sets the alias as the default model constant, from
  `f8a3040`.
- `.tickets/wisp-o2llma/` in `STATE.md`, `responses/001.md`,
  `states/001.md`, `states/005.md`-`009.md`, and `ticket.md`.
- `AI_SETUP_RECIPES.md:130`; `md/notes/opencode-go.md:53,54,107`.
- `tests/fixtures/usage_event_log.txt` and
  `tests/fixtures/usage_net_rule.txt` carry the same family slug.

### Other model aliases

The GLM, Claude, and Qwen deployment slugs appear in
`.tickets/wisp-o2llma/`, `AI_SETUP_RECIPES.md`, `md/notes/opencode-go.md`,
`md/specs/spec-001-strip-kept-reasoning.md`,
`md/specs/spec-002-segment-start-wording.md`, and `tests/fixtures/`.

### Azure URL fixture

`wisp/tests/test_providers.py:447` holds a placeholder Azure endpoint,
introduced by `e0d468f`.

### API keys

No real key found. Placeholder `sk-` strings appear only in
`.tickets/wisp-o2llma/responses/002.md`,
`.tickets/wisp-o2llma/responses/003.md`, and
`.tickets/wisp-o2llma/ticket.md:457`.

### Judged not a leak

The `x-litellm-request-id` header name in `wisp/wisp` and bare "LiteLLM"
mentions are generic public API identifiers. The `AGENTS.md` rule allows
the term "company LiteLLM server".

## Settlement, 2026-11-10

The user chose option (a) in `## Gaps`: rewrite published history and
force-push. The rewrite is done locally; no push was sent.

`git filter-branch --tree-filter` rewrote `main` from its root. All nine
commits are new. The published base moved from `e0d468f` to `f1f853a`;
the local tip moved from `54242dd` to `76b9b8f` (pre-revert hashes; the Amendment lists the current ones). The old history stays
reachable at `refs/backup/pre-scrub` and
`refs/original/refs/heads/main`.

Changed files at the tip (20 before the Amendment; 19 after):

- `.tickets/wisp-o2llma/`: `STATE.md`, `responses/001.md`,
  `responses/005.md`, `states/001.md`, `states/005.md`-`009.md`,
  `ticket.md`.
- `AI_SETUP_RECIPES.md`, `md/notes/opencode-go.md`,
  `md/specs/spec-001-strip-kept-reasoning.md`,
  `md/specs/spec-002-segment-start-wording.md`.
- `tests/fixtures/usage_event_log.txt`,
  `tests/fixtures/usage_event_log_glm.txt`,
  `tests/fixtures/usage_net_rule.txt`.
- `wispy/wispy`, `wispy/tests/test_wispy.py`, `README.md`.

What changed:

- The company gateway host became `company-litellm.example.com` in
  every URL.
- Every used deployment slug became the display name already used by
  the `.tickets/ai-wpueub/` scrub; the free OpenCode variant took a
  ` Free` suffix. Commands quote the display name.
- `wispy/wispy` no longer bakes a model into `MODEL`. `run`,
  `continue`, and `commit` exit 2 unless `--model` or `WISPY_MODEL`
  names one. The test harness passes `test-model`, and the README
  example exports `WISPY_MODEL=your-model-id`.

Left as is:

- The Azure fixture at `wisp/tests/test_providers.py:447`, per the
  user's instruction: it is generic and globally available.
- The public OpenRouter vendor-prefixed example ids in
  `AI_SETUP_RECIPES.md` and the o2llma ticket: they are generic
  provider examples, not company deployment slugs.
- Placeholder `sk-` strings (no real key), bare "LiteLLM" mentions,
  and the `x-litellm-request-id` header name.
- Untracked `wisp-sessions/` logs still hold the old URL.
  `wisp-sessions/` is gitignored, so those logs sit outside every
  commit.

Verification:

- Every commit in the new `main` scans clean for the company host, the
  deployment slugs, and real-looking keys, except the OpenCode Go ids the
  Amendment restores.
- Commit messages, authors, and dates are byte-identical to the old
  history.
- `git diff refs/backup/pre-scrub main` lists only the 20 intended
  files; the Azure fixture diff is empty.
- `python3 -m pytest wispy/tests/test_wispy.py wisp/tests -q` gives 258
  passed.
- The six `tests/test_wisp_*.sh` suites pass with 70, 4, 11, 5, 1, and
  11 checks.

Remaining owner action: force-push `main`. `main` and `origin/main`
have diverged (9 and 4 commits). Run `git fetch origin`, then
`git push --force-with-lease origin main`. After the push, delete
`refs/backup/pre-scrub`, `refs/original/refs/heads/main`, and the
`refs/jj/keep/` refs, then run `git gc --prune=now` to expunge the old
objects. `AGENTS.md` stays modified and uncommitted.

### How to review the rewrite

Commit count, messages, authors, and dates match, so the two histories pair
by position. `git range-diff` prints `=` where a commit's patch is
identical and `!` where the scrub changed it. Verified map:

- Published half `f8a3040..e0d468f` maps to `2cdbf68..35e3e0c` (the hash after the Amendment).
- Root `f8a3040` carries every scrub in `README.md`, `wispy/wispy`,
  `wispy/tests/test_wispy.py`, `md/specs/*`, and `tests/fixtures/*`.
- `4616c61`, `db3dfdf`, and `e0d468f` diverge only inside their own files.
- The five unpushed pairs (`504da4f`..`54242dd`) all report `=`, the
  already-amended `a8797fe` pair against `5b2b612` included.

Commands, run in the repo root after `git fetch origin`:

1. `git range-diff -s origin/main~3..origin/main main~8..main~5` prints the
   published pair map. `git range-diff -s f8a3040...2cdbf68` covers the
   root pair, which no range can hold.
2. `git range-diff origin/main~3..origin/main main~8..main~5` prints each
   changed patch. Add `--no-dual-color` for plain text.
3. Per-commit snapshot stat, pairing by position: `paste <(git rev-list
   --reverse origin/main) <(git rev-list --reverse main | head -4) | while
   read -r o n; do git diff --stat "$o" "$n"; done`.
4. The whole scrub as one diff: `git diff origin/main main~5`. This output
   equals `git diff refs/backup/pre-scrub main` byte for byte (388 lines, after the amendment below),
   because the five unpushed commits touch no scrubbed file.
   `git diff origin/main main` mixes the four unpushed commits' content
   into the scrub and is not the review diff.

The `-` side of every hunk holds the leaked values by construction. To read
the diff without echoing them into a log: `git diff origin/main main~5 |
sed -E '/^-/ s#https?://[^ `")]+#<URL>#g; /^-/
s/(deepseek|glm|claude|qwen)[A-Za-z0-9._-]*/<MODEL>/gi'`.

## Amendment, 2026-11-10: OpenCode Go note reverted

The user judged the `md/notes/opencode-go.md` scrub wrong: OpenCode Go is a
public service, not company internal. A second `git filter-branch
--index-filter` restored the pre-scrub blob `c8a3adf5` at
`md/notes/opencode-go.md` in every commit that carries the file. No other
path changed.

The file now carries OpenCode Go's public model ids (`deepseek-v4.1-flash`,
`deepseek-v4.1-flash-free`, `glm-5.3-flash`), matching the pre-scrub
history. The company gateway host never appeared in this file.

History after the second rewrite (nine commits, same order):

- `2cdbf68`, `99ef05e`, `f251117` unchanged (the file does not exist yet).
- `f1f853a` -> `35e3e0c`
- `19eab24` -> `190a29b`
- `5b2b612` -> `93d864d`
- `9e2f6a1` -> `db7a569`
- `f4bf5e8` -> `be33c46`
- `76b9b8f` -> `25d8c38`

Tip `25d8c38`.

Verification:

- `git diff refs/backup/pre-scrub main` lists 19 files and 388 lines; the
  `md/notes/opencode-go.md` entry is gone because both sides match, and the
  file's own diff is empty.
- Per-commit position pairing: the six rewritten pairs each differ in that
  one file only; the first three pairs are identical.
- Messages, authors, and dates match the pre-revert history byte for byte.
- `git diff origin/main main~5` equals `git diff refs/backup/pre-scrub main`
  byte for byte, 388 lines.
- Slug scan at the tip: `deepseek-v4` and `glm-5` hit only
  `md/notes/opencode-go.md`; every other slug hit is a public example id or
  ticket prose that the first settlement left as is.
- No code changed. The tree equals the tree that passed 258 pytest tests and
  the six shell suites, except for this one markdown file.

The second filter-branch overwrote `refs/original/refs/heads/main` from
`54242dd` to the pre-revert rewritten tip `76b9b8f`. The pre-scrub history
stays at `refs/backup/pre-scrub` (`54242dd`) and the `refs/jj/keep/` refs.

Remaining owner action is unchanged: force-push `main`, then delete
`refs/backup/pre-scrub`, `refs/original/refs/heads/main`, and the
`refs/jj/keep/` refs, then run `git gc --prune=now`.

## Gaps

None.
