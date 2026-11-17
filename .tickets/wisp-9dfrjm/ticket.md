---
id: 'wisp-9dfrjm'
name: 'commit updates ticket name'
status: 'closed'
created: '2026-11-17T20:19:26Z'
parent: null
blocked-on: []
---

# Situation

The commit subject froze `<status>(<id>): <name>` from the name the
ticket opened with. A ticket opens before the work is clear, so the
commit log carried requests where it should carry definitions. The last
example: `can wisp render-live stream tool calls?` became the subject of
commit `2850e59`, although the work done was
`wisp render-live: stream tool calls and their results`.

The first design exited 1 and left the amend to the operator. That is a
human gate in a step the seal session can close itself: it holds the
rules and the failure.

# Decision

The commit session writes the ticket name, and the subject carries it.

- The name rule: a definition of the work done; a short noun phrase or
  `<component>: <effect>`; lowercase; no trailing question mark; no
  interrogative or auxiliary lead word (can, should, does, is, how, why,
  what, when, which, who, will, would, could, did, has, have, ...); at
  most 12 words.
- `wispy` writes the status, the session writes the name. The rename
  travels with the work in the same commit.
- The subject is not frozen. The prompt header carries the id, the name,
  and the status, plus the form `<status>(<id>): <name>`. The session
  derives the literal from the ticket after the rename.
- `wispy` reads the committed name and `git log -1 --format=%s` after the
  commit. A name that asks a question, a name past 12 words, or a subject
  that carries another name opens one repair turn in the same session.
  The repair turn carries the failure, the ticket, and the order to fix
  the `name:` line and amend HEAD with the new subject.
- The seal has no human gate. A failure that survives the repair turn
  stands: `wispy` notes it, clears the phase, prints the commit, and
  exits 0. The repair turn continues the seal session, so the persona
  and the transcript carry the rules.
- The gate derives the status from the committed ticket, so a status
  changed inside the session also opens the repair turn instead of
  committing a stale subject.

# Tasks

- [x] `wispy/wispy`: `name_problem`, `ticket_meta`, the name rule and the
  subject gate in `cmd_commit`, the header with `Ticket name now` and the
  subject form, the module docstring.
- [x] `wispy/prompts/commit-rules.md`: `## The name`, the subject build
  rule, the widened post-commit check list, the steering carve-out.
- [x] `wispy/tests/test_wispy.py`: `log -1 --format=%s` in `FakeExec`,
  rename and gate tests, `NameProblemTests`, the rule-text tests; 112
  tests pass. The wisp suite, the tikit suite, the shell suite, and the
  seam test still pass; `TestChatGoldenBody` fails on the python3 tool
  description, a drift that predates this ticket.
- [x] `md/design/wispy.md`: the rename paragraph, the name rule, the two
  new gate rows.
- [x] `README.md`: one bullet under the `wispy` added-functionality list.
- [x] `wispy/wispy`: `seal_problem` covers the name and the subject gate,
  `cmd_commit` sends one repair turn in the same session and accepts a
  failure that survives it, `PromptService.commit_repair_turn` builds the
  turn, and the module docstring states the new exit.
- [x] `wispy/prompts/commit-rules.md`: `## The repair turn`, the amend
  carve-out in `## Decide`, and the widened check list.
- [x] `wispy/tests/test_wispy.py`: `FakeExec` fires a list of stream hooks,
  the repair-turn tests, the blind-accept test, and the rule-text test;
  114 tests pass. The wisp suite, the tikit suite, the shell suites, and
  the seam test still pass.
- [x] `md/design/wispy.md`, `README.md`: the repair turn in the gate table
  and the name paragraph.

# Out of Scope

- Renaming tickets at distill or run time. The name belongs to the seal.
- A separate naming session, or a naming call in a new session. The
  repair turn continues the seal session, which already reads the
  record and carries the rules.
- Editing the frontmatter name in this ticket now. The commit session for
  this ticket does that under the new rule.
