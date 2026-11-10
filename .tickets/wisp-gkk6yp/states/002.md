# Next

- Run `python3 wispy/tests/test_wispy.py`; expect 97 tests, OK.
- Change nothing before the user asks; the `--close` fix sits uncommitted on branch `main`.

# Open

# Cache

- `--close` is a boolean on `wispy commit`: `Opts.close`, the `FLAGS` table at `wispy/wispy:1202`, and a refusal on every other command. `mark_closed` (`wispy/wispy:367`) runs after the phase and repo gates and before the work-tree check, so the status write is record that starts the commit on an otherwise clean tree. (From: wispy/wispy, wispy/tests/test_wispy.py) (Serves: Next)
- `FakeExec.on_status` in `wispy/tests/test_wispy.py` replaces the scripted `git status` with a callback, so a test can derive the dirty tree from the fake filesystem; `test_close_makes_the_ticket_record_so_the_commit_starts` uses it. (From: wispy/tests/test_wispy.py) (Serves: Next)
- The suite needs no runner package: `python3 wispy/tests/test_wispy.py` loads the script through `SourceFileLoader` and fakes the fs, exec, and stdio; 97 tests pass after the `--close` work. (From: wispy/tests/test_wispy.py) (Serves: Next)

# Pointers

- Ticket: `.tickets/wisp-gkk6yp/ticket.md`
- Source: `wispy/wispy` (`mark_closed` at 367, `commit_subject` at 555, `commit_turn` at 627, `cmd_commit` at 1084, `FLAGS` at 1202)
- Rules: `wispy/prompts/commit-rules.md`
- Tests: `wispy/tests/test_wispy.py`
- Design doc: `md/design/wispy.md`
- Branch: `main`
- Session dir: `/home/pnagyux/code/wisp/wisp-sessions/wisp-gkk6yp-002`
