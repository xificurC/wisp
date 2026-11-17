# Next
- Nothing to build; the user seals with `wispy commit --close`.

# Open

# Cache
- `cmd_commit` checks the seal with `seal_problem`; a failure sends one `wisp run` on the same commit session with `PromptService.commit_repair_turn`, then re-checks, and accepts either way: "the seal holds after the repair turn" or "the seal still fails; the commit stands anyway"; the path then clears `.phase`, prints `git show --stat HEAD`, and exits 0. (From: `wispy/wispy` `cmd_commit`, `seal_problem`, `commit_repair_turn`) (Serves: cold)
- An `wispy commit` rerun on a clean tree prints "work tree clean; nothing to commit" and returns 0 before the seal check, so a failed repair run gets no second automatic check. (From: `wispy/wispy` `cmd_commit`, the clean-tree early return) (Serves: cold)
- `wisp/tests/test_attachments.py::TestChatGoldenBody::test_golden` fails because the pin reads "Run a python3 command and return its output." and `wisp/wisp` sends "Run Python source and return its output."; the drift predates ticket wisp-9dfrjm. (From: `python3 -m pytest wisp/tests -q`, the assertion diff) (Serves: cold)

# Pointers
- Branch `main`; uncommitted changes in `README.md`, `md/design/wispy.md`, `wispy/prompts/commit-rules.md`, `wispy/tests/test_wispy.py`, `wispy/wispy`; ticket dir `.tickets/wisp-9dfrjm/` untracked.
- Ticket dir `/home/pnagyux/code/wisp/.tickets/wisp-9dfrjm`.
- Session dirs `/home/pnagyux/code/wisp/wisp-sessions/wisp-9dfrjm-001`, `-002`, `-003`.
- Test command `python3 -m pytest wispy/tests -q`; 114 pass.
- `wispy/tests/test_wispy.py` `FakeExec.on_stream` takes one hook or a list of hooks, fired one per stream call.
