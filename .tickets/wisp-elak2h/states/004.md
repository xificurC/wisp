# Next
- If the user confirms the force-push, run `git push --force-with-lease origin main` on branch `main`.
- After the push, delete `refs/backup/pre-scrub`, `refs/original/refs/heads/main`, and the `refs/jj/keep/` refs, then run `git gc --prune=now`.
- If the user asks to commit, commit the rewritten `main` together with the uncommitted `AGENTS.md` rule.
- To review the rewrite, run the commands under ticket `### How to review the rewrite`.

# Open
None.

# Cache
- `git diff origin/main main~5` equals `git diff refs/backup/pre-scrub main` byte for byte, 388 lines over 19 files, because the five unpushed commits touch no scrubbed file. (From: two `git diff` runs, `cmp`, `wc -l`) (Serves: Next)
- The commit pairing runs by position; `main~5` is the rewritten twin of the pushed tip `origin/main`. (From: `git range-diff -s`, `git log --format`) (Serves: Next)

# Pointers
- Ticket: `/home/pnagyux/code/wisp/.tickets/wisp-elak2h/ticket.md` (status `wip`; `## Settlement` and `## Amendment` hold the rewrite records and the review recipe).
- Session dirs: `/home/pnagyux/code/wisp/wisp-sessions/wisp-elak2h-004` (this turn), `/home/pnagyux/code/wisp/wisp-sessions/wisp-elak2h-003`, `/home/pnagyux/code/wisp/wisp-sessions/wisp-elak2h-002`.
- Branch `main` carries the rewritten nine-commit history; `origin/main` still points at the old base; no push sent.
- Old history refs: `refs/backup/pre-scrub`, `refs/original/refs/heads/main`, `refs/jj/keep/*`.
- Working tree: `AGENTS.md` modified; `.tickets/wisp-elak2h/` untracked.
- Test commands: `python3 -m pytest wispy/tests/test_wispy.py wisp/tests -q`; `bash tests/test_wisp_*.sh`.
